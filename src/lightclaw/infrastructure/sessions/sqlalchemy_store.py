from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from lightclaw.domain.agent.models import AgentTurn
from lightclaw.domain.sessions.base import SessionStore
from lightclaw.infrastructure.persistence.models import SessionMessageRecord


class SqlAlchemySessionStore(SessionStore):
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    async def get_history(self, session_id: str) -> list[AgentTurn]:
        with self._session_factory() as session:
            rows = session.execute(
                select(SessionMessageRecord)
                .where(SessionMessageRecord.session_id == session_id)
                .order_by(SessionMessageRecord.id.asc())
            ).scalars()
            return [
                AgentTurn(role=row.role, content=row.content, name=row.name, created_at=row.created_at)
                for row in rows
            ]

    async def append_turn(self, session_id: str, turn: AgentTurn) -> None:
        with self._session_factory() as session:
            session.add(
                SessionMessageRecord(
                    session_id=session_id,
                    role=turn.role,
                    content=turn.content,
                    name=turn.name,
                    created_at=turn.created_at,
                )
            )
            session.commit()
