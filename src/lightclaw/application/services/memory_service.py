from lightclaw.domain.memory.base import MemoryContextProvider, MemoryStore
from lightclaw.domain.memory.models import MemoryRecord, MemoryWritePolicy, MemoryWriteRequest


class MemoryService(MemoryContextProvider):
    def __init__(
        self,
        memory_store: MemoryStore,
        write_policy: MemoryWritePolicy | None = None,
    ) -> None:
        self._memory_store = memory_store
        self._write_policy = write_policy or MemoryWritePolicy()

    async def build_context(self, user_id: str, session_id: str | None = None) -> list[str]:
        records = await self._memory_store.list_records(
            user_id=user_id,
            session_id=session_id,
            limit=10,
        )
        ordered = sorted(
            records,
            key=lambda record: (
                _scope_priority(record.scope),
                _kind_priority(record.kind),
                record.created_at,
            ),
            reverse=True,
        )
        return [record.to_context_line() for record in ordered[:10]]

    async def remember(self, request: MemoryWriteRequest) -> bool:
        if not self._write_policy.allows(request):
            return False

        existing = await self._memory_store.list_records(
            user_id=request.user_id,
            session_id=request.session_id,
            limit=100,
        )
        normalized_content = request.content.strip().lower()
        for record in existing:
            if (
                record.kind == request.kind
                and record.scope == request.scope
                and record.content.strip().lower() == normalized_content
            ):
                return False

        await self._memory_store.add_record(
            MemoryRecord(
                user_id=request.user_id,
                content=request.content.strip(),
                kind=request.kind,
                scope=request.scope,
                session_id=request.session_id,
                source=request.source,
            )
        )
        return True


def _kind_priority(kind: str) -> int:
    priorities = {
        "profile": 5,
        "preference": 4,
        "task_rule": 3,
        "project_fact": 2,
        "reminder": 1,
        "legacy": 0,
    }
    return priorities.get(kind, 0)


def _scope_priority(scope: str) -> int:
    priorities = {
        "session": 3,
        "user": 2,
        "global": 1,
    }
    return priorities.get(scope, 0)
