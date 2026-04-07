from collections import defaultdict

from lightclaw.domain.agent.models import AgentTurn
from lightclaw.domain.sessions.base import SessionStore
from lightclaw.domain.sessions.models import SessionSummary


class InMemorySessionStore(SessionStore):
    def __init__(self) -> None:
        self._sessions: dict[str, list[AgentTurn]] = defaultdict(list)

    async def get_history(self, session_id: str) -> list[AgentTurn]:
        return list(self._sessions[session_id])

    async def append_turn(self, session_id: str, turn: AgentTurn) -> None:
        self._sessions[session_id].append(turn)

    async def list_sessions(self, limit: int = 50) -> list[SessionSummary]:
        summaries: list[SessionSummary] = []
        for session_id, turns in self._sessions.items():
            if not turns:
                continue
            last_turn = turns[-1]
            summaries.append(
                SessionSummary(
                    session_id=session_id,
                    turn_count=len(turns),
                    last_role=last_turn.role,
                    preview=last_turn.content[:120],
                    updated_at=last_turn.created_at,
                )
            )
        summaries.sort(key=lambda item: item.updated_at, reverse=True)
        return summaries[:limit]
