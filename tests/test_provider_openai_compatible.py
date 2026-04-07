import asyncio
import json

import httpx

from lightclaw.bootstrap import build_container
from lightclaw.config.settings import AppSettings
from lightclaw.domain.agent.models import AgentTurn
from lightclaw.domain.providers.models import ProviderConfig
from lightclaw.infrastructure.providers.openai_compatible import OpenAICompatibleProvider
from lightclaw.infrastructure.tools.registry import InMemoryToolRegistry


def test_bootstrap_selects_openai_compatible_provider() -> None:
    container = build_container(
        AppSettings(
            provider_backend="openai_compatible",
            provider_base_url="https://example.test/v1",
            provider_api_key="secret",
            storage_backend="memory",
        )
    )

    assert type(container.provider).__name__ == "OpenAICompatibleProvider"


def test_openai_compatible_provider_normalizes_text_response() -> None:
    async def _run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path.endswith("/chat/completions")
            payload = json.loads(request.content.decode("utf-8"))
            assert payload["model"] == "test-model"
            assert payload["messages"][0]["role"] == "system"
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "hello from provider"}}],
                    "usage": {"prompt_tokens": 11, "completion_tokens": 3, "total_tokens": 14},
                },
            )

        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://example.test/v1",
        )
        provider = OpenAICompatibleProvider(
            ProviderConfig(
                backend="openai_compatible",
                model="test-model",
                base_url="https://example.test/v1",
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

        assert response.final_text == "hello from provider"
        assert response.usage["total_tokens"] == 14
        await client.aclose()

    asyncio.run(_run())


def test_openai_compatible_provider_normalizes_tool_calls() -> None:
    async def _run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {
                                            "name": "echo.text",
                                            "arguments": "{\"text\":\"hi\"}",
                                        },
                                    }
                                ]
                            }
                        }
                    ],
                    "usage": {"prompt_tokens": 9, "completion_tokens": 2, "total_tokens": 11},
                },
            )

        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://example.test/v1",
        )
        provider = OpenAICompatibleProvider(
            ProviderConfig(
                backend="openai_compatible",
                model="test-model",
                base_url="https://example.test/v1",
                api_key="secret",
            ),
            http_client=client,
        )
        response = await provider.generate_next(
            message="/tool echo.text hi",
            history=[AgentTurn(role="user", content="/tool echo.text hi")],
            memories=[],
            instructions=[],
            tool_registry=InMemoryToolRegistry(),
        )

        assert response.final_text is None
        assert response.tool_calls[0].name == "echo.text"
        assert response.tool_calls[0].arguments == {"text": "hi"}
        assert response.usage["total_tokens"] == 11
        await client.aclose()

    asyncio.run(_run())


def test_openai_compatible_provider_streams_delta_events() -> None:
    async def _run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            content = (
                'data: {"choices":[{"delta":{"content":"hello "}}]}\n\n'
                'data: {"choices":[{"delta":{"content":"stream"}}],"usage":{"total_tokens":7}}\n\n'
                "data: [DONE]\n\n"
            )
            return httpx.Response(200, text=content)

        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://example.test/v1",
        )
        provider = OpenAICompatibleProvider(
            ProviderConfig(
                backend="openai_compatible",
                model="test-model",
                base_url="https://example.test/v1",
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
        assert "".join(event.text or "" for event in events) == "hello stream"
        assert events[-1].usage["total_tokens"] == 7
        await client.aclose()

    asyncio.run(_run())
