import asyncio

from lightclaw.domain.agent.models import AgentTurn
from lightclaw.domain.providers.models import ProviderConfig
from lightclaw.infrastructure.providers.anthropic import AnthropicProvider
from lightclaw.infrastructure.providers.mock import MockProvider
from lightclaw.infrastructure.providers.openai_compatible import OpenAICompatibleProvider
from lightclaw.infrastructure.tools.registry import InMemoryToolRegistry


def test_provider_profiles_report_streaming_capability() -> None:
    mock_provider = MockProvider()
    openai_provider = OpenAICompatibleProvider(
        ProviderConfig(
            backend="openai_compatible",
            model="gpt-test",
            base_url="https://example.test/v1",
            api_key="secret",
        )
    )
    anthropic_provider = AnthropicProvider(
        ProviderConfig(
            backend="anthropic",
            model="claude-test",
            base_url="https://example.test",
            api_key="secret",
        )
    )

    assert mock_provider.profile().supports_streaming is False
    assert openai_provider.profile().supports_streaming is True
    assert anthropic_provider.profile().supports_streaming is True


def test_default_stream_next_emits_completed_event() -> None:
    async def _run() -> None:
        provider = MockProvider()
        events = []
        async for event in provider.stream_next(
            message="hello",
            history=[AgentTurn(role="user", content="hello")],
            memories=[],
            instructions=[],
            tool_registry=InMemoryToolRegistry(),
        ):
            events.append(event)

        assert len(events) == 1
        assert events[0].event_type == "completed"
        assert "hello" in (events[0].text or "")

    asyncio.run(_run())
