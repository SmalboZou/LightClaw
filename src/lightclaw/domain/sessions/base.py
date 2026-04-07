from abc import ABC, abstractmethod

from lightclaw.domain.agent.models import AgentTurn


class SessionStore(ABC):
    @abstractmethod
    async def get_history(self, session_id: str) -> list[AgentTurn]:
        raise NotImplementedError

    @abstractmethod
    async def append_turn(self, session_id: str, turn: AgentTurn) -> None:
        raise NotImplementedError
