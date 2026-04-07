import asyncio

import httpx
import pytest

from lightclaw.bootstrap import build_container
from lightclaw.config.settings import AppSettings
from lightclaw.domain.agent.models import AgentTurn
from lightclaw.domain.errors import ProviderRequestError
from lightclaw.domain.providers.models import ProviderConfig
from lightclaw.infrastructure.providers.anthropic import AnthropicProvider
from lightclaw.infrastructure.tools.registry import InMemoryToolRegistry


def test_bootstrap_selects_anthropic_provider() -> None:
    container = build_container(
        AppSettings(
            provider_backend="anthropic",
            provider_model="claude-3-5-sonnet-latest",
            provider_base_url="https://example.test",
            provider_api_key="secret",
            storage_backend="memory",
        )
    )

    assert type(container.provider).__name__ == "AnthropicProvider"


def test_anthropic_provider_normalizes_text_and_tool_use() -> None:
    async def _run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path.endswith("/v1/messages")
            return httpx.Response(
                200,
                json={
                    "content": [
                        {"type": "text", "text": "Before tool."},
                        {"type": "tool_use", "id": "toolu_1", "name": "echo.text", "input": {"text": "hi"}},
                    ],
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
            )

        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://example.test",
        )
        provider = AnthropicProvider(
            ProviderConfig(
                backend="anthropic",
                model="claude-test",
                base_url="https://example.test",
                api_key="secret",
            ),
            http_client=client,
        )
        response = await provider.generate_next(
            message="hello",
            history=[AgentTurn(role="user", content="hello")],
            memories=["remember me"],
            instructions=[],
            tool_registry=InMemoryToolRegistry(),
        )

        assert response.final_text == "Before tool."
        assert response.tool_calls[0].name == "echo.text"
        assert response.tool_calls[0].arguments == {"text": "hi"}
        assert response.usage["input_tokens"] == 10
        await client.aclose()

    asyncio.run(_run())


def test_provider_config_requires_model_and_base_url() -> None:
    with pytest.raises(ValueError):
        ProviderConfig(backend="anthropic")


def test_openai_compatible_wraps_http_errors() -> None:
    async def _run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"error": "boom"})

        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://example.test/v1",
        )
        provider = AnthropicProvider(
            ProviderConfig(
                backend="anthropic",
                model="claude-test",
                base_url="https://example.test",
                api_key="secret",
            ),
            http_client=client,
        )

        try:
            await provider.generate_next(
                message="hello",
                history=[AgentTurn(role="user", content="hello")],
                memories=[],
                instructions=[],
                tool_registry=InMemoryToolRegistry(),
            )
        except ProviderRequestError:
            await client.aclose()
            return

        await client.aclose()
        raise AssertionError("Expected ProviderRequestError")

    asyncio.run(_run())


def test_anthropic_provider_streams_delta_events() -> None:
    async def _run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            content = (
                'data: {"type":"content_block_delta","delta":{"text":"hello "}}\n\n'
                'data: {"type":"content_block_delta","delta":{"text":"anthropic"}}\n\n'
                'data: {"type":"message_delta","usage":{"input_tokens":8,"output_tokens":4}}\n\n'
                'data: {"type":"message_stop"}\n\n'
            )
            return httpx.Response(200, text=content)

        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://example.test",
        )
        provider = AnthropicProvider(
            ProviderConfig(
                backend="anthropic",
                model="claude-test",
                base_url="https://example.test",
                api_key="secret",
            ),
            http_client=client,
        )

        events = []
        async for event in provider.stream_next(
            message="hello",
            history=[AgentTurn(role="user", content="hello")],
            memories=[],
            instructions=[],
            tool_registry=InMemoryToolRegistry(),
        ):
            events.append(event)

        assert [event.event_type for event in events] == ["delta", "delta", "completed"]
        assert "".join(event.text or "" for event in events) == "hello anthropic"
        assert events[-1].usage["input_tokens"] == 8
        await client.aclose()

    asyncio.run(_run())
