import asyncio
from datetime import UTC, datetime

from lightclaw.application.services.job_service import JobService
from lightclaw.domain.jobs.models import JobDefinition
from lightclaw.domain.logs.base import ExecutionLogStore


class SchedulerService:
    def __init__(
        self,
        job_service: JobService,
        execution_log_store: ExecutionLogStore,
        poll_seconds: int = 30,
    ) -> None:
        self._job_service = job_service
        self._execution_log_store = execution_log_store
        self._poll_seconds = poll_seconds
        self._task: asyncio.Task | None = None
        self._last_tick_key: str | None = None

    async def list_due_jobs(self, now: datetime) -> list[JobDefinition]:
        jobs = await self._job_service.list_jobs()
        return [job for job in jobs if job.enabled and _cron_matches(job.cron, now)]

    async def run_due_jobs(self, now: datetime) -> list[JobDefinition]:
        due_jobs = await self.list_due_jobs(now)
        executed: list[JobDefinition] = []
        for job in due_jobs:
            executed.append(await self._job_service.run_job(job.job_id))
        return executed

    async def run_pending_tick(self, now: datetime | None = None) -> list[JobDefinition]:
        current = now or datetime.now(UTC)
        tick_key = current.strftime("%Y-%m-%dT%H:%M")
        if tick_key == self._last_tick_key:
            return []

        self._last_tick_key = tick_key
        executed = await self.run_due_jobs(current)
        await self._execution_log_store.record(
            event_type="scheduler_tick",
            message=f"tick={tick_key} executed={len(executed)}",
            session_id="scheduler",
        )
        return executed

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._run_loop(), name="lightclaw-scheduler")
        await self._execution_log_store.record(
            event_type="scheduler_started",
            message=f"poll_seconds={self._poll_seconds}",
            session_id="scheduler",
        )

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        await self._execution_log_store.record(
            event_type="scheduler_stopped",
            message="stopped",
            session_id="scheduler",
        )

    def status(self) -> dict[str, object]:
        running = self._task is not None and not self._task.done()
        return {
            "running": running,
            "poll_seconds": self._poll_seconds,
            "last_tick_key": self._last_tick_key,
        }

    async def _run_loop(self) -> None:
        while True:
            await self.run_pending_tick(datetime.now(UTC))
            await asyncio.sleep(self._poll_seconds)


def _cron_matches(cron: str, now: datetime) -> bool:
    parts = cron.split()
    if len(parts) != 5:
        return False
    minute, hour, day, month, weekday = parts
    values = [
        (minute, now.minute),
        (hour, now.hour),
        (day, now.day),
        (month, now.month),
        (weekday, now.weekday()),
    ]
    return all(_match_part(pattern, value) for pattern, value in values)


def _match_part(pattern: str, value: int) -> bool:
    if pattern == "*":
        return True
    try:
        return int(pattern) == value
    except ValueError:
        return False
