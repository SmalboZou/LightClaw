from abc import ABC, abstractmethod
from typing import AsyncIterator

from lightclaw.domain.agent.models import AgentTurn
from lightclaw.domain.providers.models import (
    MemoryExtractionCandidate,
    ProviderProfile,
    ProviderResponse,
    ProviderStreamEvent,
)
from lightclaw.domain.tools.base import ToolRegistry


class ModelProvider(ABC):
    @abstractmethod
    def profile(self) -> ProviderProfile:
        raise NotImplementedError

    @abstractmethod
    async def generate_next(
        self,
        message: str,
        history: list[AgentTurn],
        memories: list[str],
        instructions: list[str],
        tool_registry: ToolRegistry,
    ) -> ProviderResponse:
        raise NotImplementedError

    async def stream_next(
        self,
        message: str,
        history: list[AgentTurn],
        memories: list[str],
        instructions: list[str],
        tool_registry: ToolRegistry,
    ) -> AsyncIterator[ProviderStreamEvent]:
        response = await self.generate_next(
            message,
            history,
            memories,
            instructions,
            tool_registry,
        )
        yield ProviderStreamEvent(
            event_type="completed",
            text=response.final_text,
            usage=response.usage,
        )

    async def extract_memories(
        self,
        user_message: str,
        assistant_reply: str,
    ) -> list[MemoryExtractionCandidate]:
        return []
