from datetime import UTC, datetime
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Header, HTTPException

from lightclaw.bootstrap import ApplicationContainer, build_container
from lightclaw.config.settings import AppSettings
from lightclaw.domain.agent.models import AgentRequest
from lightclaw.interfaces.api.errors import register_exception_handlers
from lightclaw.interfaces.api.job_models import (
    JobPayload,
    JobResponse,
    JobTriggerResponse,
    SchedulerStatusResponse,
)
from lightclaw.interfaces.api.models import ChatPayload, ChatResponse, HealthResponse, SkillResponse
from lightclaw.interfaces.telegram.models import TelegramWebhookAck, TelegramWebhookPayload


def create_api(
    settings: AppSettings,
    container: ApplicationContainer | None = None,
) -> FastAPI:
    container = container or build_container(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.scheduler_enabled:
            await container.scheduler_service.start()
        try:
            yield
        finally:
            await container.scheduler_service.stop()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    register_exception_handlers(app)
    router = APIRouter()

    @router.get("/health")
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", app=settings.app_name)

    @router.post("/chat")
    async def chat(payload: ChatPayload) -> ChatResponse:
        response = await container.chat_service.chat(
            AgentRequest(
                session_id=payload.session_id,
                user_id=payload.user_id,
                message=payload.message,
                channel=payload.channel,
                skills=payload.skills,
            )
        )
        return ChatResponse(
            session_id=payload.session_id,
            reply=response.reply,
            tool_results=response.tool_results,
        )

    @router.get("/skills")
    async def list_skills() -> list[SkillResponse]:
        skills = await container.skill_service.list_skills()
        return [
            SkillResponse(
                skill_id=skill.skill_id,
                name=skill.name,
                description=skill.description,
                tools=skill.tools,
            )
            for skill in skills
        ]

    @router.post("/telegram/webhook")
    async def telegram_webhook(
        payload: TelegramWebhookPayload,
        x_telegram_bot_api_secret_token: str | None = Header(default=None),
    ) -> TelegramWebhookAck:
        if settings.telegram_webhook_secret:
            if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
                raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret.")
        return await container.telegram_service.handle_webhook(payload)

    @router.get("/jobs")
    async def list_jobs() -> list[JobResponse]:
        jobs = await container.job_service.list_jobs()
        return [_job_to_response(job) for job in jobs]

    @router.post("/jobs")
    async def upsert_job(payload: JobPayload) -> JobResponse:
        from lightclaw.domain.jobs.models import JobDefinition

        job = JobDefinition(
            job_id=payload.job_id,
            name=payload.name,
            cron=payload.cron,
            enabled=payload.enabled,
            input_prompt=payload.input_prompt,
            target_channel=payload.target_channel,
            target_destination=payload.target_destination,
            skills=payload.skills,
            policy_mode=payload.policy_mode,
        )
        await container.job_service.upsert_job(job)
        return _job_to_response(job)

    @router.post("/jobs/{job_id}/run")
    async def run_job(job_id: str) -> JobTriggerResponse:
        job = await container.job_service.run_job(job_id)
        return JobTriggerResponse(
            job_id=job.job_id,
            status=job.last_status or "unknown",
            last_output=job.last_output,
        )

    @router.post("/scheduler/run-due")
    async def run_due_jobs() -> list[JobTriggerResponse]:
        jobs = await container.scheduler_service.run_due_jobs(datetime.now(UTC))
        return [
            JobTriggerResponse(
                job_id=job.job_id,
                status=job.last_status or "unknown",
                last_output=job.last_output,
            )
            for job in jobs
        ]

    @router.get("/scheduler/status")
    async def scheduler_status() -> SchedulerStatusResponse:
        return SchedulerStatusResponse(**container.scheduler_service.status())

    @router.post("/scheduler/start")
    async def scheduler_start() -> SchedulerStatusResponse:
        await container.scheduler_service.start()
        return SchedulerStatusResponse(**container.scheduler_service.status())

    @router.post("/scheduler/stop")
    async def scheduler_stop() -> SchedulerStatusResponse:
        await container.scheduler_service.stop()
        return SchedulerStatusResponse(**container.scheduler_service.status())

    @router.post("/scheduler/tick")
    async def scheduler_tick() -> list[JobTriggerResponse]:
        jobs = await container.scheduler_service.run_pending_tick(datetime.now(UTC))
        return [
            JobTriggerResponse(
                job_id=job.job_id,
                status=job.last_status or "unknown",
                last_output=job.last_output,
            )
            for job in jobs
        ]

    app.include_router(router)
    return app


def _job_to_response(job) -> JobResponse:
    return JobResponse(
        job_id=job.job_id,
        name=job.name,
        cron=job.cron,
        enabled=job.enabled,
        input_prompt=job.input_prompt,
        target_channel=job.target_channel,
        target_destination=job.target_destination,
        skills=job.skills,
        policy_mode=job.policy_mode,
        last_status=job.last_status,
        last_run_at=job.last_run_at,
        last_output=job.last_output,
    )
