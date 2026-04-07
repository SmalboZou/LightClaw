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


class AnthropicProvider(ModelProvider):
    """Adapter for Anthropic messages API."""

    def __init__(
        self,
        config: ProviderConfig,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self._http_client = http_client or httpx.AsyncClient(
            base_url=(config.base_url or "https://api.anthropic.com").rstrip("/"),
            timeout=30.0,
        )
        self._owns_client = http_client is None

    def profile(self) -> ProviderProfile:
        return ProviderProfile(
            backend="anthropic",
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
            "max_tokens": 1024,
            "system": self._build_system(memories, instructions),
            "messages": self._build_messages(history),
            "tools": await self._build_tools(tool_registry),
        }
        try:
            response = await self._http_client.post(
                "/v1/messages",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderRequestError(f"Anthropic request failed: {exc}") from exc
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
            "max_tokens": 1024,
            "system": self._build_system(memories, instructions),
            "messages": self._build_messages(history),
            "tools": await self._build_tools(tool_registry),
            "stream": True,
        }
        try:
            async with self._http_client.stream(
                "POST",
                "/v1/messages",
                headers=self._headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
                usage: dict[str, int] = {}
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line.removeprefix("data: ").strip()
                    if not data:
                        continue
                    chunk = json.loads(data)
                    chunk_type = chunk.get("type")
                    if chunk_type == "content_block_delta":
                        text = chunk.get("delta", {}).get("text")
                        if text:
                            yield ProviderStreamEvent(event_type="delta", text=text)
                    elif chunk_type == "message_delta":
                        usage = self._normalize_usage(chunk.get("usage", {}))
                    elif chunk_type == "message_stop":
                        yield ProviderStreamEvent(event_type="completed", usage=usage)
                        return
        except httpx.HTTPError as exc:
            raise ProviderRequestError(f"Anthropic streaming request failed: {exc}") from exc

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http_client.aclose()

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        if self._config.api_key:
            headers["x-api-key"] = self._config.api_key
        return headers

    def _build_system(self, memories: list[str], instructions: list[str]) -> str | None:
        parts: list[str] = []
        if memories:
            memory_block = "\n".join(f"- {memory}" for memory in memories)
            parts.append(f"Relevant long-term memory:\n{memory_block}")
        if instructions:
            instruction_block = "\n\n".join(instructions)
            parts.append(f"Active skill instructions:\n{instruction_block}")
        if not parts:
            return None
        return "\n\n".join(parts)

    def _build_messages(self, history: list[AgentTurn]) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        for turn in history:
            if turn.role == "tool":
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": turn.name or "tool",
                                "content": turn.content,
                            }
                        ],
                    }
                )
            else:
                messages.append({"role": turn.role, "content": turn.content})
        return messages

    async def _build_tools(self, tool_registry: ToolRegistry) -> list[dict[str, Any]]:
        tools = await tool_registry.list_tools()
        return [
            {
                "name": tool.definition().name,
                "description": tool.definition().description,
                "input_schema": tool.definition().argument_schema
                or {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": True,
                },
            }
            for tool in tools
        ]

    def _normalize_response(self, payload: dict[str, Any]) -> ProviderResponse:
        blocks = payload.get("content", [])
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in blocks:
            block_type = block.get("type")
            if block_type == "text":
                text_parts.append(block.get("text", ""))
            elif block_type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        name=block["name"],
                        arguments=block.get("input", {}) if isinstance(block.get("input"), dict) else {},
                    )
                )

        final_text = "".join(text_parts) if text_parts else None
        usage = self._normalize_usage(payload.get("usage", {}))
        if tool_calls:
            return ProviderResponse(final_text=final_text, tool_calls=tool_calls, usage=usage)
        return ProviderResponse(final_text=final_text or "", usage=usage)

    def _normalize_usage(self, usage: dict[str, Any]) -> dict[str, int]:
        normalized: dict[str, int] = {}
        for key, value in usage.items():
            if isinstance(value, int):
                normalized[key] = value
        return normalized
