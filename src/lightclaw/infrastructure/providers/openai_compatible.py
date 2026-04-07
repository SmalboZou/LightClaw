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
        payload = {
            "model": self._config.model,
            "messages": self._build_messages(history, memories, instructions),
            "tools": await self._build_tools(tool_registry),
            "tool_choice": "auto",
        }
        try:
            response = await self._http_client.post(
                "/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderRequestError(f"OpenAI-compatible request failed: {exc}") from exc
        return self._normalize_response(response.json())

    async def stream_next(
        self,
        message: str,
        history: list[AgentTurn],
        memories: list[str],
        instructions: list[str],
        tool_registry: ToolRegistry,
    ) -> AsyncIterator[ProviderStreamEvent]:
        payload = {
            "model": self._config.model,
            "messages": self._build_messages(history, memories, instructions),
            "tools": await self._build_tools(tool_registry),
            "tool_choice": "auto",
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        try:
            async with self._http_client.stream(
                "POST",
                "/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as response:
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
            raise ProviderRequestError(f"OpenAI-compatible streaming request failed: {exc}") from exc

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http_client.aclose()

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
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
