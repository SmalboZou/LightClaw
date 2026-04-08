from datetime import UTC, datetime

from lightclaw.domain.logs.base import ExecutionLogStore


class InMemoryExecutionLogStore(ExecutionLogStore):
    def __init__(self) -> None:
        self._events: list[dict[str, str]] = []

    async def record(
        self,
        event_type: str,
        message: str,
        session_id: str | None = None,
        run_id: str | None = None,
    ) -> None:
        self._events.append(
            {
                "event_type": event_type,
                "message": message,
                "session_id": session_id or "",
                "run_id": run_id or "",
                "created_at": datetime.now(UTC).isoformat(),
            }
        )

    async def list_events(
        self,
        session_id: str | None = None,
        run_id: str | None = None,
    ) -> list[dict[str, str]]:
        events = list(self._events)
        if session_id is not None:
            events = [event for event in events if event["session_id"] == session_id]
        if run_id is not None:
            events = [event for event in events if event["run_id"] == run_id]
        return events
