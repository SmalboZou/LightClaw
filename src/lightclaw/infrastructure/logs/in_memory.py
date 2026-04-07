from lightclaw.domain.logs.base import ExecutionLogStore


class InMemoryExecutionLogStore(ExecutionLogStore):
    def __init__(self) -> None:
        self._events: list[dict[str, str]] = []

    async def record(self, event_type: str, message: str, session_id: str | None = None) -> None:
        self._events.append(
            {
                "event_type": event_type,
                "message": message,
                "session_id": session_id or "",
            }
        )

    async def list_events(self, session_id: str | None = None) -> list[dict[str, str]]:
        if session_id is None:
            return list(self._events)
        return [event for event in self._events if event["session_id"] == session_id]
