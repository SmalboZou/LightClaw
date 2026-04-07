from abc import ABC, abstractmethod

from lightclaw.domain.memory.models import MemoryRecord


class MemoryContextProvider(ABC):
    @abstractmethod
    async def build_context(self, user_id: str, session_id: str | None = None) -> list[str]:
        raise NotImplementedError


class MemoryStore(ABC):
    @abstractmethod
    async def get_memories(self, user_id: str, session_id: str | None = None) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    async def add_memory(self, user_id: str, memory: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list_records(
        self,
        user_id: str,
        session_id: str | None = None,
        limit: int = 20,
    ) -> list[MemoryRecord]:
        raise NotImplementedError

    @abstractmethod
    async def add_record(self, record: MemoryRecord) -> None:
        raise NotImplementedError
