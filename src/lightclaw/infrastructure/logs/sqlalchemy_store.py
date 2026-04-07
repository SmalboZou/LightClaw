from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from lightclaw.domain.logs.base import ExecutionLogStore
from lightclaw.infrastructure.persistence.models import ExecutionLogRecord


class SqlAlchemyExecutionLogStore(ExecutionLogStore):
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    async def record(self, event_type: str, message: str, session_id: str | None = None) -> None:
        with self._session_factory() as session:
            session.add(
                ExecutionLogRecord(
                    session_id=session_id,
                    event_type=event_type,
                    message=message,
                )
            )
            session.commit()

    async def list_events(self, session_id: str | None = None) -> list[dict[str, str]]:
        with self._session_factory() as session:
            query = select(ExecutionLogRecord).order_by(ExecutionLogRecord.id.asc())
            if session_id is not None:
                query = query.where(ExecutionLogRecord.session_id == session_id)
            rows = session.execute(query).scalars()
            return [
                {
                    "event_type": row.event_type,
                    "message": row.message,
                    "session_id": row.session_id or "",
                }
                for row in rows
            ]
