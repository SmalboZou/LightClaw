from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from lightclaw.domain.errors import (
    AgentLoopExceededError,
    AuthenticationError,
    AuthorizationError,
    JobDisabledError,
    JobNotFoundError,
    JobRunNotFoundError,
    LightClawError,
    PolicyViolationError,
    ProviderRequestError,
    ToolArgumentValidationError,
    SkillDependencyError,
    SkillNotFoundError,
    ToolNotFoundError,
)
from lightclaw.interfaces.api.models import ErrorResponse


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(PolicyViolationError)
    async def handle_policy_violation(
        request: Request, exc: PolicyViolationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content=ErrorResponse(
                error_code="policy_violation",
                message=str(exc),
            ).model_dump(),
        )

    @app.exception_handler(AuthenticationError)
    async def handle_authentication_error(
        request: Request, exc: AuthenticationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content=ErrorResponse(
                error_code="authentication_error",
                message=str(exc),
            ).model_dump(),
        )

    @app.exception_handler(AuthorizationError)
    async def handle_authorization_error(
        request: Request, exc: AuthorizationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content=ErrorResponse(
                error_code="authorization_error",
                message=str(exc),
            ).model_dump(),
        )

    @app.exception_handler(ToolNotFoundError)
    async def handle_tool_not_found(
        request: Request, exc: ToolNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error_code="tool_not_found",
                message=str(exc),
            ).model_dump(),
        )

    @app.exception_handler(ToolArgumentValidationError)
    async def handle_tool_argument_validation(
        request: Request, exc: ToolArgumentValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error_code="tool_argument_validation_error",
                message=str(exc),
            ).model_dump(),
        )

    @app.exception_handler(JobNotFoundError)
    async def handle_job_not_found(
        request: Request, exc: JobNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error_code="job_not_found",
                message=str(exc),
            ).model_dump(),
        )

    @app.exception_handler(JobDisabledError)
    async def handle_job_disabled(
        request: Request, exc: JobDisabledError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content=ErrorResponse(
                error_code="job_disabled",
                message=str(exc),
            ).model_dump(),
        )

    @app.exception_handler(JobRunNotFoundError)
    async def handle_job_run_not_found(
        request: Request, exc: JobRunNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error_code="job_run_not_found",
                message=str(exc),
            ).model_dump(),
        )

    @app.exception_handler(ProviderRequestError)
    async def handle_provider_error(
        request: Request, exc: ProviderRequestError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(
                error_code="provider_request_error",
                message=str(exc),
            ).model_dump(),
        )

    @app.exception_handler(SkillNotFoundError)
    async def handle_skill_not_found(
        request: Request, exc: SkillNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                error_code="skill_not_found",
                message=str(exc),
            ).model_dump(),
        )

    @app.exception_handler(SkillDependencyError)
    async def handle_skill_dependency_error(
        request: Request, exc: SkillDependencyError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content=ErrorResponse(
                error_code="skill_dependency_error",
                message=str(exc),
            ).model_dump(),
        )

    @app.exception_handler(AgentLoopExceededError)
    async def handle_loop_error(
        request: Request, exc: AgentLoopExceededError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error_code="agent_loop_error",
                message=str(exc),
            ).model_dump(),
        )

    @app.exception_handler(LightClawError)
    async def handle_lightclaw_error(
        request: Request, exc: LightClawError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error_code="lightclaw_error",
                message=str(exc),
            ).model_dump(),
        )
