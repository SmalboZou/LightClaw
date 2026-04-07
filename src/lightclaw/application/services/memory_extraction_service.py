from lightclaw.application.services.memory_service import MemoryService
from lightclaw.domain.memory.models import MemoryWriteRequest
from lightclaw.domain.providers.base import ModelProvider


class MemoryExtractionService:
    def __init__(
        self,
        provider: ModelProvider,
        memory_service: MemoryService,
    ) -> None:
        self._provider = provider
        self._memory_service = memory_service

    async def extract_and_remember(
        self,
        *,
        user_id: str,
        session_id: str,
        user_message: str,
        assistant_reply: str,
    ) -> int:
        candidates = await self._provider.extract_memories(
            user_message=user_message,
            assistant_reply=assistant_reply,
        )
        written = 0
        for candidate in candidates:
            stored = await self._memory_service.remember(
                MemoryWriteRequest(
                    user_id=user_id,
                    content=candidate.content,
                    kind=candidate.kind,
                    scope=candidate.scope,
                    session_id=session_id if candidate.scope == "session" else None,
                    source="extraction",
                )
            )
            if stored:
                written += 1
        return written
