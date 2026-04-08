import uuid
from datetime import UTC, datetime

from lightclaw.application.services.chat_service import ChatService
from lightclaw.domain.errors import JobDisabledError, JobNotFoundError, JobRunNotFoundError
from lightclaw.domain.jobs.base import JobStore
from lightclaw.domain.jobs.models import JobDefinition, JobRun
from lightclaw.domain.logs.base import ExecutionLogStore
from lightclaw.interfaces.feishu.sender import FeishuSender
from lightclaw.interfaces.telegram.sender import TelegramSender


class JobService:
    def __init__(
        self,
        job_store: JobStore,
        chat_service: ChatService,
        execution_log_store: ExecutionLogStore,
        telegram_sender: TelegramSender | None = None,
        feishu_sender: FeishuSender | None = None,
    ) -> None:
        self._job_store = job_store
        self._chat_service = chat_service
        self._execution_log_store = execution_log_store
        self._telegram_sender = telegram_sender
        self._feishu_sender = feishu_sender

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

    async def list_job_runs(self, job_id: str | None = None) -> list[JobRun]:
        return await self._job_store.list_job_runs(job_id)

    async def get_job_run(self, run_id: str) -> JobRun:
        job_run = await self._job_store.get_job_run(run_id)
        if job_run is None:
            raise JobRunNotFoundError(f"Job run '{run_id}' was not found.")
        return job_run

    async def run_job(self, job_id: str) -> JobDefinition:
        job = await self._job_store.get_job(job_id)
        if job is None:
            raise JobNotFoundError(f"Job '{job_id}' was not found.")
        if not job.enabled:
            raise JobDisabledError(f"Job '{job_id}' is disabled.")

        run = JobRun(
            run_id=str(uuid.uuid4()),
            job_id=job.job_id,
            trigger="manual",
            status="running",
            input_prompt=job.input_prompt,
            started_at=datetime.now(UTC),
        )
        await self._job_store.record_job_run(run)
        session_id = f"job:{job.job_id}"
        await self._execution_log_store.record(
            event_type="job_started",
            message=f"job_id={job.job_id} run_id={run.run_id}",
            session_id=session_id,
            run_id=run.run_id,
        )

        from lightclaw.domain.agent.models import AgentRequest

        try:
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
            if (
                job.target_channel == "feishu"
                and job.target_destination
                and self._feishu_sender is not None
            ):
                receive_id_type, receive_id = _parse_feishu_destination(job.target_destination)
                await self._feishu_sender.send_message(
                    receive_id=receive_id,
                    text=response.reply,
                    receive_id_type=receive_id_type,
                )

            job.last_status = "completed"
            job.last_run_at = datetime.now(UTC)
            job.last_output = response.reply
            await self._job_store.upsert_job(job)
            run.status = "completed"
            run.output_text = response.reply
            run.completed_at = datetime.now(UTC)
            await self._job_store.record_job_run(run)
            await self._execution_log_store.record(
                event_type="job_completed",
                message=f"job_id={job.job_id} run_id={run.run_id}",
                session_id=session_id,
                run_id=run.run_id,
            )
            return job
        except Exception as exc:
            job.last_status = "failed"
            job.last_run_at = datetime.now(UTC)
            job.last_output = str(exc)
            await self._job_store.upsert_job(job)
            run.status = "failed"
            run.error_message = str(exc)
            run.completed_at = datetime.now(UTC)
            await self._job_store.record_job_run(run)
            await self._execution_log_store.record(
                event_type="job_failed",
                message=f"job_id={job.job_id} run_id={run.run_id} error={exc}",
                session_id=session_id,
                run_id=run.run_id,
            )
            raise


def _parse_feishu_destination(destination: str) -> tuple[str, str]:
    normalized = destination.strip()
    if ":" not in normalized:
        return "chat_id", normalized
    receive_id_type, receive_id = normalized.split(":", 1)
    if receive_id_type in {"chat_id", "open_id", "union_id", "user_id", "email"} and receive_id:
        return receive_id_type, receive_id
    return "chat_id", normalized
