import json
from datetime import UTC, datetime
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Cookie, FastAPI, Header, HTTPException, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from lightclaw.bootstrap import ApplicationContainer, build_container
from lightclaw.config.settings import AppSettings
from lightclaw.domain.agent.models import AgentRequest
from lightclaw.domain.errors import AuthenticationError
from lightclaw.domain.providers.models import ProviderConfig
from lightclaw.infrastructure.providers.anthropic import AnthropicProvider
from lightclaw.infrastructure.persistence.database import get_migration_status
from lightclaw.infrastructure.providers.mock import MockProvider
from lightclaw.infrastructure.providers.openai_compatible import OpenAICompatibleProvider
from lightclaw.infrastructure.tools.registry import InMemoryToolRegistry
from lightclaw.interfaces.api.console_models import (
    ConsoleAuthPayload,
    ConsoleAuthResponse,
    ConsoleBootstrapPayload,
    ConsoleChatPayload,
    ConsoleConfigResponse,
    ConsoleConfigUpdatePayload,
    ConsoleConfigUpdateResponse,
    ConsoleCreateUserPayload,
    ConsoleProviderTestPayload,
    ConsoleProviderTestResponse,
    ConsoleSetupStatusResponse,
    ConsoleSystemStatusResponse,
    ExecutionLogResponse,
    SessionDetailResponse,
    SessionSummaryResponse,
    ToolDefinitionResponse,
    ConsoleUserResponse,
)
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
    static_root = Path(__file__).resolve().parent.parent / "webconsole" / "static"

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
    app.mount("/console/assets", StaticFiles(directory=static_root), name="console-assets")

    def _require_console_user(console_session: str | None) -> dict[str, str]:
        return container.console_auth_service.resolve_session(console_session)

    def _provider_from_payload(payload: ConsoleProviderTestPayload):
        active_settings = container.settings
        provider_api_key = payload.provider_api_key or active_settings.provider_api_key
        provider_extra_headers = (
            _parse_extra_headers(payload.provider_extra_headers_json)
            if payload.provider_extra_headers_json.strip()
            else active_settings.provider_extra_headers
        )
        if payload.provider_backend == "openai_compatible":
            return OpenAICompatibleProvider(
                ProviderConfig(
                    backend=payload.provider_backend,
                    model=payload.provider_model,
                    base_url=payload.provider_base_url or "https://api.openai.com/v1",
                    api_key=provider_api_key,
                    extra_headers=provider_extra_headers,
                )
            )
        if payload.provider_backend == "anthropic":
            return AnthropicProvider(
                ProviderConfig(
                    backend=payload.provider_backend,
                    model=payload.provider_model,
                    base_url=payload.provider_base_url or "https://api.anthropic.com",
                    api_key=provider_api_key,
                )
            )
        return MockProvider()

    @router.get("/health")
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", app=settings.app_name)

    @router.get("/console", include_in_schema=False)
    async def console_index() -> FileResponse:
        return FileResponse(static_root / "index.html")

    @router.get("/console/", include_in_schema=False)
    async def console_index_slash() -> FileResponse:
        return FileResponse(static_root / "index.html")

    @router.get("/console/api/setup/status")
    async def console_setup_status() -> ConsoleSetupStatusResponse:
        return ConsoleSetupStatusResponse(
            **container.console_auth_service.get_setup_status()
        )

    @router.post("/console/api/setup/bootstrap")
    async def console_bootstrap(
        payload: ConsoleBootstrapPayload,
        response: Response,
    ) -> ConsoleAuthResponse:
        user = container.console_auth_service.bootstrap_admin(
            payload.admin_username,
            payload.admin_password,
        )
        await container.config_service.save_console_config(
            {
                "provider_backend": payload.provider_backend,
                "provider_model": payload.provider_model,
                "provider_base_url": payload.provider_base_url,
                "provider_extra_headers_json": payload.provider_extra_headers_json,
                "provider_api_key": payload.provider_api_key,
                "storage_backend": payload.storage_backend,
                "tool_policy": payload.tool_policy,
                "allow_process_exec": payload.allow_process_exec,
                "allow_network_access": payload.allow_network_access,
                "console_admin_username": payload.admin_username,
                "console_admin_password": payload.admin_password,
            }
        )
        container.reload_runtime(
            AppSettings(
                workspace_root=settings.workspace_root,
                _env_file=settings.workspace_root / ".env",
            )
        )
        token, auth_user = container.console_auth_service.login(
            payload.admin_username,
            payload.admin_password,
        )
        response.set_cookie(
            key="lightclaw_console_session",
            value=token,
            httponly=True,
            samesite="lax",
        )
        return ConsoleAuthResponse(
            authenticated=True,
            user=ConsoleUserResponse(
                username=auth_user["username"],
                role=auth_user["role"],
                created_at=user.get("created_at"),
            ),
        )

    @router.post("/console/api/auth/login")
    async def console_login(
        payload: ConsoleAuthPayload,
        response: Response,
    ) -> ConsoleAuthResponse:
        token, user = container.console_auth_service.login(payload.username, payload.password)
        response.set_cookie(
            key="lightclaw_console_session",
            value=token,
            httponly=True,
            samesite="lax",
        )
        return ConsoleAuthResponse(
            authenticated=True,
            user=ConsoleUserResponse(
                username=user["username"],
                role=user["role"],
            ),
        )

    @router.post("/console/api/auth/logout")
    async def console_logout(
        response: Response,
        lightclaw_console_session: str | None = Cookie(default=None),
    ) -> ConsoleAuthResponse:
        container.console_auth_service.logout(lightclaw_console_session)
        response.delete_cookie("lightclaw_console_session")
        return ConsoleAuthResponse(authenticated=False, user=None)

    @router.get("/console/api/auth/me")
    async def console_auth_me(
        lightclaw_console_session: str | None = Cookie(default=None),
    ) -> ConsoleAuthResponse:
        try:
            user = _require_console_user(lightclaw_console_session)
        except AuthenticationError:
            return ConsoleAuthResponse(authenticated=False, user=None)
        return ConsoleAuthResponse(
            authenticated=True,
            user=ConsoleUserResponse(username=user["username"], role=user["role"]),
        )

    @router.get("/console/api/users")
    async def console_users(
        lightclaw_console_session: str | None = Cookie(default=None),
    ) -> list[ConsoleUserResponse]:
        actor = _require_console_user(lightclaw_console_session)
        users = container.console_auth_service.list_users(actor)
        return [ConsoleUserResponse(**user) for user in users]

    @router.post("/console/api/users")
    async def console_create_user(
        payload: ConsoleCreateUserPayload,
        lightclaw_console_session: str | None = Cookie(default=None),
    ) -> ConsoleUserResponse:
        actor = _require_console_user(lightclaw_console_session)
        user = container.console_auth_service.create_user(
            actor,
            payload.username,
            payload.password,
            payload.role,
        )
        return ConsoleUserResponse(**user)

    @router.get("/console/api/config")
    async def console_config(
        lightclaw_console_session: str | None = Cookie(default=None),
    ) -> ConsoleConfigResponse:
        _require_console_user(lightclaw_console_session)
        return ConsoleConfigResponse(**(await container.config_service.get_console_config()))

    @router.post("/console/api/config")
    async def console_save_config(
        payload: ConsoleConfigUpdatePayload,
        lightclaw_console_session: str | None = Cookie(default=None),
    ) -> ConsoleConfigUpdateResponse:
        _require_console_user(lightclaw_console_session)
        result = await container.config_service.save_console_config(payload.model_dump())
        if not result["requires_restart"]:
            container.reload_runtime(
                AppSettings(
                    workspace_root=settings.workspace_root,
                    _env_file=settings.workspace_root / ".env",
                )
            )
        return ConsoleConfigUpdateResponse(**result)

    @router.post("/console/api/provider/test")
    async def console_test_provider(
        payload: ConsoleProviderTestPayload,
        lightclaw_console_session: str | None = Cookie(default=None),
    ) -> ConsoleProviderTestResponse:
        _require_console_user(lightclaw_console_session)
        provider = _provider_from_payload(payload)
        if payload.provider_backend == "mock":
            return ConsoleProviderTestResponse(
                ok=True,
                backend="mock",
                model="mock",
                message="Mock provider is always available.",
            )
        from lightclaw.domain.agent.models import AgentTurn
        result = await provider.generate_next(
            message="Reply with OK.",
            history=[AgentTurn(role="user", content="Reply with OK.")],
            memories=[],
            instructions=[],
            tool_registry=container.tool_registry,
        )
        return ConsoleProviderTestResponse(
            ok=True,
            backend=payload.provider_backend,
            model=payload.provider_model,
            message=result.final_text or "Provider connection succeeded.",
        )

    @router.get("/console/api/tools")
    async def console_tools(
        lightclaw_console_session: str | None = Cookie(default=None),
    ) -> list[ToolDefinitionResponse]:
        _require_console_user(lightclaw_console_session)
        tools = await container.tool_registry.list_tools()
        return [ToolDefinitionResponse.from_definition(tool.definition()) for tool in tools]

    @router.get("/console/api/sessions")
    async def console_sessions(
        lightclaw_console_session: str | None = Cookie(default=None),
    ) -> list[SessionSummaryResponse]:
        user = _require_console_user(lightclaw_console_session)
        sessions = await container.session_store.list_sessions()
        owned_ids = set(
            container.console_ownership_service.list_owned_sessions(
                [session.session_id for session in sessions],
                user["username"],
            )
        )
        return [
            SessionSummaryResponse(**session.model_dump())
            for session in sessions
            if session.session_id in owned_ids
        ]

    @router.get("/console/api/sessions/{session_id}")
    async def console_session_detail(
        session_id: str,
        lightclaw_console_session: str | None = Cookie(default=None),
    ) -> SessionDetailResponse:
        user = _require_console_user(lightclaw_console_session)
        container.console_ownership_service.ensure_session_access(session_id, user["username"])
        turns = await container.session_store.get_history(session_id)
        return SessionDetailResponse(session_id=session_id, turns=turns)

    @router.get("/console/api/logs")
    async def console_logs(
        session_id: str | None = None,
        lightclaw_console_session: str | None = Cookie(default=None),
    ) -> list[ExecutionLogResponse]:
        user = _require_console_user(lightclaw_console_session)
        if session_id is not None:
            container.console_ownership_service.ensure_session_access(session_id, user["username"])
        events = await container.execution_log_store.list_events(session_id=session_id)
        return [ExecutionLogResponse(**event) for event in events]

    @router.get("/console/api/system")
    async def console_system(
        lightclaw_console_session: str | None = Cookie(default=None),
    ) -> ConsoleSystemStatusResponse:
        _require_console_user(lightclaw_console_session)
        migration_status = get_migration_status(settings.database_url)
        scheduler_status = container.scheduler_service.status()
        return ConsoleSystemStatusResponse(
            app_name=settings.app_name,
            env=settings.env,
            storage_backend=settings.storage_backend,
            provider_backend=settings.provider_backend,
            provider_model=settings.provider_model,
            scheduler_running=bool(scheduler_status["running"]),
            scheduler_poll_seconds=int(scheduler_status["poll_seconds"]),
            current_schema_version=migration_status["current_version"],
            latest_schema_version=migration_status["latest_version"],
            pending_schema_versions=list(migration_status["pending_versions"]),
        )

    @router.post("/console/api/chat")
    async def console_chat(
        payload: ConsoleChatPayload,
        lightclaw_console_session: str | None = Cookie(default=None),
    ) -> ChatResponse:
        user = _require_console_user(lightclaw_console_session)
        container.console_ownership_service.claim_session(payload.session_id, user["username"])
        response = await container.chat_service.chat(
            AgentRequest(
                session_id=payload.session_id,
                user_id=f"console:{user['username']}",
                message=payload.message,
                channel="console",
                skills=payload.skills,
            )
        )
        return ChatResponse(
            session_id=payload.session_id,
            reply=response.reply,
            tool_results=response.tool_results,
        )

    @router.post("/console/api/chat/stream")
    async def console_chat_stream(
        payload: ConsoleChatPayload,
        lightclaw_console_session: str | None = Cookie(default=None),
    ) -> StreamingResponse:
        user = _require_console_user(lightclaw_console_session)
        container.console_ownership_service.claim_session(payload.session_id, user["username"])

        async def event_stream():
            yield "event: status\ndata: " + json.dumps({"message": "started"}) + "\n\n"
            try:
                response = await container.chat_service.chat(
                    AgentRequest(
                        session_id=payload.session_id,
                        user_id=f"console:{user['username']}",
                        message=payload.message,
                        channel="console",
                        skills=payload.skills,
                    )
                )
                for chunk in _chunk_text(response.reply):
                    yield "event: delta\ndata: " + json.dumps({"text": chunk}) + "\n\n"
                for tool_result in response.tool_results:
                    yield (
                        "event: tool_result\ndata: "
                        + json.dumps(tool_result.model_dump())
                        + "\n\n"
                    )
                yield (
                    "event: completed\ndata: "
                    + json.dumps(
                        {
                            "session_id": response.session_id,
                            "reply": response.reply,
                        }
                    )
                    + "\n\n"
                )
            except Exception as exc:
                yield (
                    "event: error\ndata: "
                    + json.dumps({"message": str(exc)})
                    + "\n\n"
                )

        return StreamingResponse(event_stream(), media_type="text/event-stream")

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

    @router.get("/console/api/jobs")
    async def console_list_jobs(
        lightclaw_console_session: str | None = Cookie(default=None),
    ) -> list[JobResponse]:
        user = _require_console_user(lightclaw_console_session)
        jobs = await container.job_service.list_jobs()
        owned_ids = set(
            container.console_ownership_service.list_owned_jobs(
                [job.job_id for job in jobs],
                user["username"],
            )
        )
        return [_job_to_response(job) for job in jobs if job.job_id in owned_ids]

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

    @router.post("/console/api/jobs")
    async def console_upsert_job(
        payload: JobPayload,
        lightclaw_console_session: str | None = Cookie(default=None),
    ) -> JobResponse:
        user = _require_console_user(lightclaw_console_session)
        container.console_ownership_service.claim_job(payload.job_id, user["username"])
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

    @router.post("/console/api/jobs/{job_id}/run")
    async def console_run_job(
        job_id: str,
        lightclaw_console_session: str | None = Cookie(default=None),
    ) -> JobTriggerResponse:
        user = _require_console_user(lightclaw_console_session)
        container.console_ownership_service.ensure_job_access(job_id, user["username"])
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


def _chunk_text(text: str, size: int = 32) -> list[str]:
    return [text[index : index + size] for index in range(0, len(text), size)] or [""]


def _parse_extra_headers(value: str) -> dict[str, str]:
    if not value.strip():
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        str(key): str(item)
        for key, item in payload.items()
        if isinstance(key, str) and isinstance(item, str)
    }
