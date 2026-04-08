from abc import ABC, abstractmethod

from lightclaw.domain.agent.models import AgentTurn
from lightclaw.domain.sessions.models import SessionSummary


class SessionStore(ABC):
    @abstractmethod
    async def get_history(self, session_id: str) -> list[AgentTurn]:
        raise NotImplementedError

    @abstractmethod
    async def append_turn(self, session_id: str, turn: AgentTurn) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list_sessions(self, limit: int = 50) -> list[SessionSummary]:
        raise NotImplementedError
