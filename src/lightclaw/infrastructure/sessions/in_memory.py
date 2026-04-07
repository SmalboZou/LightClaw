from collections import defaultdict

from lightclaw.domain.agent.models import AgentTurn
from lightclaw.domain.sessions.base import SessionStore


class InMemorySessionStore(SessionStore):
    def __init__(self) -> None:
        self._sessions: dict[str, list[AgentTurn]] = defaultdict(list)

    async def get_history(self, session_id: str) -> list[AgentTurn]:
        return list(self._sessions[session_id])

    async def append_turn(self, session_id: str, turn: AgentTurn) -> None:
        self._sessions[session_id].append(turn)
