from collections import defaultdict

from lightclaw.domain.memory.base import MemoryStore
from lightclaw.domain.memory.models import MemoryRecord


class InMemoryMemoryStore(MemoryStore):
    def __init__(self) -> None:
        self._items: dict[str, list[MemoryRecord]] = defaultdict(list)

    async def get_memories(self, user_id: str, session_id: str | None = None) -> list[str]:
        records = await self.list_records(user_id=user_id, session_id=session_id, limit=20)
        return [
            record.content if record.kind == "legacy" else record.to_context_line()
            for record in records
        ]

    async def add_memory(self, user_id: str, memory: str) -> None:
        await self.add_record(MemoryRecord(user_id=user_id, content=memory, kind="legacy"))

    async def list_records(
        self,
        user_id: str,
        session_id: str | None = None,
        limit: int = 20,
    ) -> list[MemoryRecord]:
        records = list(self._items[user_id])
        if session_id is not None:
            records = [
                record
                for record in records
                if record.scope != "session" or record.session_id == session_id
            ]
        return records[:limit]

    async def add_record(self, record: MemoryRecord) -> None:
        self._items[record.user_id].append(record)
