from abc import ABC, abstractmethod


class ExecutionLogStore(ABC):
    @abstractmethod
    async def record(
        self,
        event_type: str,
        message: str,
        session_id: str | None = None,
        run_id: str | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list_events(
        self,
        session_id: str | None = None,
        run_id: str | None = None,
    ) -> list[dict[str, str]]:
        raise NotImplementedError
