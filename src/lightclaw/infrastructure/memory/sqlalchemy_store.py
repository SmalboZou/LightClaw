import json

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from lightclaw.domain.memory.base import MemoryStore
from lightclaw.domain.memory.models import MemoryRecord
from lightclaw.infrastructure.persistence.models import MemoryRecord as DbMemoryRecord


class SqlAlchemyMemoryStore(MemoryStore):
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

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
        with self._session_factory() as session:
            rows = session.execute(
                select(DbMemoryRecord)
                .where(DbMemoryRecord.user_id == user_id)
                .order_by(DbMemoryRecord.id.asc())
            ).scalars()
            records = [self._deserialize(row.user_id, row.content, row.created_at) for row in rows]
            if session_id is not None:
                records = [
                    record
                    for record in records
                    if record.scope != "session" or record.session_id == session_id
                ]
            return records[:limit]

    async def add_record(self, record: MemoryRecord) -> None:
        with self._session_factory() as session:
            session.add(
                DbMemoryRecord(
                    user_id=record.user_id,
                    content=self._serialize(record),
                    created_at=record.created_at,
                )
            )
            session.commit()

    def _serialize(self, record: MemoryRecord) -> str:
        return record.model_dump_json()

    def _deserialize(self, user_id: str, raw_content: str, created_at) -> MemoryRecord:
        try:
            payload = json.loads(raw_content)
        except json.JSONDecodeError:
            return MemoryRecord(
                user_id=user_id,
                content=raw_content,
                kind="legacy",
                created_at=created_at,
            )
        if not isinstance(payload, dict):
            return MemoryRecord(
                user_id=user_id,
                content=raw_content,
                kind="legacy",
                created_at=created_at,
            )
        payload.setdefault("user_id", user_id)
        payload.setdefault("created_at", created_at)
        return MemoryRecord(**payload)
