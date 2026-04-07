from datetime import UTC, datetime

from lightclaw.application.services.chat_service import ChatService
from lightclaw.domain.errors import JobDisabledError, JobNotFoundError
from lightclaw.domain.jobs.base import JobStore
from lightclaw.domain.jobs.models import JobDefinition
from lightclaw.domain.logs.base import ExecutionLogStore
from lightclaw.interfaces.telegram.sender import TelegramSender


class JobService:
    def __init__(
        self,
        job_store: JobStore,
        chat_service: ChatService,
        execution_log_store: ExecutionLogStore,
        telegram_sender: TelegramSender | None = None,
    ) -> None:
        self._job_store = job_store
        self._chat_service = chat_service
        self._execution_log_store = execution_log_store
        self._telegram_sender = telegram_sender

    async def upsert_job(self, job: JobDefinition) -> None:
        await self._job_store.upsert_job(job)
        await self._execution_log_store.record(
            event_type="job_upserted",
            message=f"job_id={job.job_id} enabled={job.enabled}",
            session_id=f"job:{job.job_id}",
        )

    async def get_job(self, job_id: str) -> JobDefinition | None:
        return await self._job_store.get_job(job_id)

    async def list_jobs(self) -> list[JobDefinition]:
        return await self._job_store.list_jobs()

    async def run_job(self, job_id: str) -> JobDefinition:
        job = await self._job_store.get_job(job_id)
        if job is None:
            raise JobNotFoundError(f"Job '{job_id}' was not found.")
        if not job.enabled:
            raise JobDisabledError(f"Job '{job_id}' is disabled.")

        session_id = f"job:{job.job_id}"
        await self._execution_log_store.record(
            event_type="job_started",
            message=f"job_id={job.job_id}",
            session_id=session_id,
        )

        from lightclaw.domain.agent.models import AgentRequest

        response = await self._chat_service.chat(
            AgentRequest(
                session_id=session_id,
                user_id=f"job:{job.job_id}",
                message=job.input_prompt,
                channel="scheduler",
                skills=job.skills,
            )
        )

        if (
            job.target_channel == "telegram"
            and job.target_destination
            and self._telegram_sender is not None
        ):
            await self._telegram_sender.send_message(
                chat_id=job.target_destination,
                text=response.reply,
            )

        job.last_status = "completed"
        job.last_run_at = datetime.now(UTC)
        job.last_output = response.reply
        await self._job_store.upsert_job(job)
        await self._execution_log_store.record(
            event_type="job_completed",
            message=f"job_id={job.job_id}",
            session_id=session_id,
        )
        return job
