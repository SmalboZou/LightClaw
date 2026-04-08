import asyncio
import json

import httpx

from lightclaw.bootstrap import build_container
from lightclaw.config.settings import AppSettings
from lightclaw.domain.agent.models import AgentTurn
from lightclaw.domain.providers.models import ProviderConfig
from lightclaw.domain.tools.base import ToolRegistry
from lightclaw.infrastructure.providers.openai_compatible import OpenAICompatibleProvider
from lightclaw.infrastructure.tools.registry import InMemoryToolRegistry


class EmptyToolRegistry(ToolRegistry):
    async def get_tool(self, name: str):
        return None

    async def list_tools(self):
        return []

    async def list_tool_names(self):
        return []


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


def test_openai_compatible_provider_merges_custom_headers() -> None:
    async def _run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["Authorization"] == "Bearer secret"
            assert request.headers["HTTP-Referer"] == "https://your-app.example"
            assert request.headers["X-Title"] == "LightClaw"
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "ok"}}],
                    "usage": {"total_tokens": 1},
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
                extra_headers={
                    "HTTP-Referer": "https://your-app.example",
                    "X-Title": "LightClaw",
                },
            ),
            http_client=client,
        )
        response = await provider.generate_next(
            message="hello",
            history=[AgentTurn(role="user", content="hello")],
            memories=[],
            instructions=[],
            tool_registry=InMemoryToolRegistry(),
        )

        assert response.final_text == "ok"
        await client.aclose()

    asyncio.run(_run())


def test_openai_compatible_provider_surfaces_upstream_error_detail() -> None:
    async def _run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                401,
                json={"error": {"message": "No auth credentials found"}},
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
                api_key="bad-key",
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
        except Exception as exc:
            assert "401" in str(exc)
            assert "No auth credentials found" in str(exc)
        else:
            raise AssertionError("Expected provider request to fail.")
        await client.aclose()

    asyncio.run(_run())


def test_openai_compatible_provider_omits_tool_choice_when_no_tools() -> None:
    async def _run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content.decode("utf-8"))
            assert "tools" not in payload
            assert "tool_choice" not in payload
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "ok"}}],
                    "usage": {"total_tokens": 1},
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
            memories=[],
            instructions=[],
            tool_registry=EmptyToolRegistry(),
        )
        assert response.final_text == "ok"
        await client.aclose()

    asyncio.run(_run())


def test_openai_compatible_provider_retries_without_tools_on_tool_related_400() -> None:
    async def _run() -> None:
        attempts: list[dict[str, object]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content.decode("utf-8"))
            attempts.append(payload)
            if "tools" in payload:
                return httpx.Response(
                    400,
                    json={"error": {"message": "This model does not support tools."}},
                )
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "fallback ok"}}],
                    "usage": {"total_tokens": 1},
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
            memories=[],
            instructions=[],
            tool_registry=InMemoryToolRegistry(),
        )

        assert response.final_text == "fallback ok"
        assert len(attempts) == 2
        assert "tools" in attempts[0]
        assert "tools" not in attempts[1]
        assert "tool_choice" not in attempts[1]
        await client.aclose()

    asyncio.run(_run())
