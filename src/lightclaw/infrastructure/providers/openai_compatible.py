import json
from typing import Any, AsyncIterator

import httpx

from lightclaw.domain.agent.models import AgentTurn, ToolCall
from lightclaw.domain.errors import ProviderRequestError
from lightclaw.domain.providers.base import ModelProvider
from lightclaw.domain.providers.models import (
    ProviderConfig,
    ProviderProfile,
    ProviderResponse,
    ProviderStreamEvent,
)
from lightclaw.domain.tools.base import ToolRegistry


class OpenAICompatibleProvider(ModelProvider):
    """Adapter for OpenAI-compatible chat completion endpoints."""

    def __init__(
        self,
        config: ProviderConfig,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self._http_client = http_client or httpx.AsyncClient(
            base_url=(config.base_url or "https://api.openai.com/v1").rstrip("/"),
            timeout=30.0,
        )
        self._owns_client = http_client is None

    def profile(self) -> ProviderProfile:
        return ProviderProfile(
            backend="openai_compatible",
            model=self._config.model,
            supports_tools=True,
            supports_streaming=True,
            supports_usage_reporting=True,
        )

    async def generate_next(
        self,
        message: str,
        history: list[AgentTurn],
        memories: list[str],
        instructions: list[str],
        tool_registry: ToolRegistry,
    ) -> ProviderResponse:
        tools = await self._build_tools(tool_registry)
        payload = {
            "model": self._config.model,
            "messages": self._build_messages(history, memories, instructions),
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        response = await self._post_with_tool_fallback(payload)
        return self._normalize_response(response.json())

    async def stream_next(
        self,
        message: str,
        history: list[AgentTurn],
        memories: list[str],
        instructions: list[str],
        tool_registry: ToolRegistry,
    ) -> AsyncIterator[ProviderStreamEvent]:
        tools = await self._build_tools(tool_registry)
        payload = {
            "model": self._config.model,
            "messages": self._build_messages(history, memories, instructions),
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        try:
            async with self._stream_with_tool_fallback(payload) as response:
                response.raise_for_status()
                usage: dict[str, int] = {}
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line.removeprefix("data: ").strip()
                    if data == "[DONE]":
                        yield ProviderStreamEvent(
                            event_type="completed",
                            usage=usage,
                        )
                        return
                    chunk = json.loads(data)
                    choice = chunk.get("choices", [{}])[0]
                    delta = choice.get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield ProviderStreamEvent(event_type="delta", text=content)
                    if "usage" in chunk and isinstance(chunk["usage"], dict):
                        usage = self._normalize_usage(chunk["usage"])
        except httpx.HTTPError as exc:
            raise ProviderRequestError(
                _provider_error_message("OpenAI-compatible streaming", exc)
            ) from exc

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http_client.aclose()

    async def _post_with_tool_fallback(self, payload: dict[str, Any]) -> httpx.Response:
        try:
            response = await self._http_client.post(
                "/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            if _should_retry_without_tools(payload, exc.response):
                fallback_payload = _without_tools(payload)
                fallback_response = await self._http_client.post(
                    "/chat/completions",
                    headers=self._headers(),
                    json=fallback_payload,
                )
                fallback_response.raise_for_status()
                return fallback_response
            raise ProviderRequestError(_provider_error_message("OpenAI-compatible", exc)) from exc
        except httpx.HTTPError as exc:
            raise ProviderRequestError(_provider_error_message("OpenAI-compatible", exc)) from exc

    def _stream_with_tool_fallback(
        self,
        payload: dict[str, Any],
    ):
        request_payload = payload
        return _FallbackStreamContextManager(
            self._http_client,
            self._headers(),
            request_payload,
        )

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", **self._config.extra_headers}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"
        return headers

    def _build_messages(
        self,
        history: list[AgentTurn],
        memories: list[str],
        instructions: list[str],
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        system_parts: list[str] = []
        if memories:
            memory_block = "\n".join(f"- {memory}" for memory in memories)
            system_parts.append(f"Relevant long-term memory:\n{memory_block}")
        if instructions:
            instruction_block = "\n\n".join(instructions)
            system_parts.append(f"Active skill instructions:\n{instruction_block}")
        if system_parts:
            messages.append({"role": "system", "content": "\n\n".join(system_parts)})

        for turn in history:
            if turn.role == "tool":
                messages.append(
                    {
                        "role": "tool",
                        "content": turn.content,
                        "name": turn.name or "tool",
                    }
                )
            else:
                messages.append({"role": turn.role, "content": turn.content})
        return messages

    async def _build_tools(self, tool_registry: ToolRegistry) -> list[dict[str, Any]]:
        tools = await tool_registry.list_tools()
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.definition().name,
                    "description": tool.definition().description,
                    "parameters": tool.definition().argument_schema
                    or {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": True,
                    },
                },
            }
            for tool in tools
        ]

    def _normalize_response(self, payload: dict[str, Any]) -> ProviderResponse:
        if "error" in payload:
            detail = payload.get("error")
            if isinstance(detail, dict):
                message = detail.get("message") or detail.get("code") or "Provider returned error"
            else:
                message = str(detail)
            raise ProviderRequestError(f"OpenAI-compatible request failed: {message}")
        choice = payload["choices"][0]["message"]
        usage = payload.get("usage", {})
        tool_calls = choice.get("tool_calls") or []
        if tool_calls:
            normalized_calls = [
                ToolCall(
                    name=call["function"]["name"],
                    arguments=self._parse_arguments(call["function"].get("arguments", "{}")),
                )
                for call in tool_calls
            ]
            return ProviderResponse(tool_calls=normalized_calls, usage=self._normalize_usage(usage))

        content = choice.get("content")
        if isinstance(content, list):
            text_parts = [part.get("text", "") for part in content if part.get("type") == "text"]
            final_text = "".join(text_parts)
        else:
            final_text = content or ""
        return ProviderResponse(final_text=final_text, usage=self._normalize_usage(usage))

    def _normalize_usage(self, usage: dict[str, Any]) -> dict[str, int]:
        return {
            key: int(value)
            for key, value in usage.items()
            if isinstance(value, int | float)
        }

    def _parse_arguments(self, raw_arguments: str) -> dict[str, Any]:
        try:
            parsed = json.loads(raw_arguments)
        except json.JSONDecodeError:
            return {"raw": raw_arguments}
        return parsed if isinstance(parsed, dict) else {"value": parsed}


def _provider_error_message(prefix: str, exc: httpx.HTTPError) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        detail = _extract_error_detail(exc.response)
        return f"{prefix} request failed ({status}): {detail}"
    return f"{prefix} request failed: {exc}"


def _extract_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text or response.reason_phrase

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
            code = error.get("code")
            if isinstance(code, str) and code.strip():
                return code.strip()
        message = payload.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    return response.text or response.reason_phrase


def _without_tools(payload: dict[str, Any]) -> dict[str, Any]:
    fallback_payload = dict(payload)
    fallback_payload.pop("tools", None)
    fallback_payload.pop("tool_choice", None)
    return fallback_payload


def _should_retry_without_tools(payload: dict[str, Any], response: httpx.Response) -> bool:
    if response.status_code != 400 or "tools" not in payload:
        return False
    detail = _extract_error_detail(response).lower()
    tool_markers = (
        "tool",
        "function calling",
        "tool_choice",
        "tools are not supported",
        "does not support tools",
        "unsupported parameter",
    )
    return any(marker in detail for marker in tool_markers) or not detail


class _FallbackStreamContextManager:
    def __init__(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> None:
        self._client = client
        self._headers = headers
        self._payload = payload
        self._context = None
        self._response = None

    async def __aenter__(self) -> httpx.Response:
        self._context = self._client.stream(
            "POST",
            "/chat/completions",
            headers=self._headers,
            json=self._payload,
        )
        response = await self._context.__aenter__()
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            await self._context.__aexit__(type(exc), exc, exc.__traceback__)
            if not _should_retry_without_tools(self._payload, exc.response):
                raise
            fallback_payload = _without_tools(self._payload)
            self._context = self._client.stream(
                "POST",
                "/chat/completions",
                headers=self._headers,
                json=fallback_payload,
            )
            response = await self._context.__aenter__()
            response.raise_for_status()
        self._response = response
        return response

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._context is not None:
            await self._context.__aexit__(exc_type, exc, tb)
