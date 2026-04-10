import asyncio
import logging
import re

from lightclaw.domain.agent.models import (
    AgentRequest,
    AgentResponse,
    AgentTurn,
    ToolCall,
    ToolResult,
)
from lightclaw.domain.errors import (
    AgentLoopExceededError,
    PolicyViolationError,
    ToolArgumentValidationError,
    ToolNotFoundError,
)
from lightclaw.domain.logs.base import ExecutionLogStore
from lightclaw.domain.memory.base import MemoryContextProvider
from lightclaw.domain.providers.base import ModelProvider
from lightclaw.domain.sessions.base import SessionStore
from lightclaw.domain.tools.base import ToolRegistry
from lightclaw.domain.tools.models import ExecutionPolicy, ToolExecutionContext
from lightclaw.domain.tools.validation import validate_tool_arguments


logger = logging.getLogger(__name__)
MAX_TOOL_OUTPUT_CHARS = 2000
_SENSITIVE_PATTERNS = [
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s]+"),
    re.compile(r"(?i)(x-api-key\s*:\s*)[^\s]+"),
]


class AgentRuntime:
    """Bounded think-act-observe-reply loop for the first working iteration."""

    def __init__(
        self,
        provider: ModelProvider,
        session_store: SessionStore,
        memory_service: MemoryContextProvider,
        tool_registry: ToolRegistry,
        policy: ExecutionPolicy,
        execution_log_store: ExecutionLogStore,
        max_loops: int = 4,
        provider_timeout_seconds: float = 15.0,
        tool_timeout_seconds: float = 10.0,
    ) -> None:
        self._provider = provider
        self._session_store = session_store
        self._memory_service = memory_service
        self._tool_registry = tool_registry
        self._policy = policy
        self._execution_log_store = execution_log_store
        self._max_loops = max_loops
        self._provider_timeout_seconds = provider_timeout_seconds
        self._tool_timeout_seconds = tool_timeout_seconds

    async def run(
        self,
        request: AgentRequest,
        *,
        tool_registry: ToolRegistry | None = None,
        instructions: list[str] | None = None,
    ) -> AgentResponse:
        resolved_tool_registry = tool_registry or self._tool_registry
        resolved_instructions = instructions or []
        history = await self._session_store.get_history(request.session_id)
        memories = await self._memory_service.build_context(
            user_id=request.user_id,
            session_id=request.session_id,
        )
        user_turn = AgentTurn(role="user", content=request.message)

        await self._session_store.append_turn(request.session_id, user_turn)
        working_history = [*history, user_turn]
        tool_results: list[ToolResult] = []

        logger.info(
            "agent_run_started session_id=%s user_id=%s channel=%s",
            request.session_id,
            request.user_id,
            request.channel,
        )
        await self._execution_log_store.record(
            event_type="agent_run_started",
            message=f"user_id={request.user_id} channel={request.channel}",
            session_id=request.session_id,
        )

        for iteration in range(self._max_loops):
            provider_response = await asyncio.wait_for(
                self._provider.generate_next(
                    message=request.message,
                    history=working_history,
                    memories=memories,
                    instructions=resolved_instructions,
                    tool_registry=resolved_tool_registry,
                ),
                timeout=self._provider_timeout_seconds,
            )

            if provider_response.final_text is not None:
                final_response = AgentResponse(
                    session_id=request.session_id,
                    reply=provider_response.final_text,
                    tool_results=tool_results,
                )
                await self._session_store.append_turn(
                    request.session_id,
                    AgentTurn(role="assistant", content=final_response.reply),
                )
                logger.info(
                    "agent_run_completed session_id=%s iterations=%s tool_results=%s",
                    request.session_id,
                    iteration + 1,
                    len(tool_results),
                )
                await self._execution_log_store.record(
                    event_type="agent_run_completed",
                    message=f"iterations={iteration + 1} tool_results={len(tool_results)}",
                    session_id=request.session_id,
                )
                return final_response

            if not provider_response.tool_calls:
                await self._execution_log_store.record(
                    event_type="agent_run_invalid_provider_response",
                    message="Provider returned neither text nor tool calls.",
                    session_id=request.session_id,
                )
                raise AgentLoopExceededError("Provider returned neither text nor tool calls.")

            for tool_call in provider_response.tool_calls:
                result = await self._execute_tool(
                    tool_call,
                    request,
                    working_history,
                    tool_registry=resolved_tool_registry,
                )
                tool_results.append(result)
                tool_turn = AgentTurn(role="tool", content=result.output, name=result.name)
                working_history.append(tool_turn)
                await self._session_store.append_turn(request.session_id, tool_turn)

        raise AgentLoopExceededError("Agent loop exceeded the configured maximum iterations.")

    async def _execute_tool(
        self,
        tool_call: ToolCall,
        request: AgentRequest,
        working_history: list[AgentTurn],
        *,
        tool_registry: ToolRegistry,
    ) -> ToolResult:
        tool = await tool_registry.get_tool(tool_call.name)
        if tool is None:
            await self._execution_log_store.record(
                event_type="tool_not_found",
                message=f"tool={tool_call.name}",
                session_id=request.session_id,
            )
            raise ToolNotFoundError(f"Tool '{tool_call.name}' is not registered.")
        try:
            validate_tool_arguments(tool.definition().argument_schema, tool_call.arguments)
        except ToolArgumentValidationError as exc:
            await self._execution_log_store.record(
                event_type="tool_argument_validation_failed",
                message=f"tool={tool.name} error={exc}",
                session_id=request.session_id,
            )
            raise
        if not self._policy.allows(tool.required_scope):
            await self._execution_log_store.record(
                event_type="tool_policy_denied",
                message=f"tool={tool.name} required_scope={tool.required_scope} policy={self._policy.mode}",
                session_id=request.session_id,
            )
            raise PolicyViolationError(
                f"Tool '{tool.name}' requires scope '{tool.required_scope}' but "
                f"policy mode is '{self._policy.mode}'."
            )

        logger.info(
            "tool_execution_started session_id=%s tool=%s scope=%s",
            request.session_id,
            tool.name,
            tool.required_scope,
        )
        await self._execution_log_store.record(
            event_type="tool_execution_started",
            message=f"tool={tool.name} scope={tool.required_scope}",
            session_id=request.session_id,
        )

        context = ToolExecutionContext(
            session_id=request.session_id,
            user_id=request.user_id,
            workspace_root=self._policy.workspace_root,
            allow_process_exec=self._policy.allow_process_exec,
            allow_network_access=self._policy.allow_network_access,
            allowed_commands=self._policy.allowed_commands,
            browser_enabled=self._policy.browser_enabled,
            browser_backend=self._policy.browser_backend,
            browser_headless=self._policy.browser_headless,
            browser_allowed_domains=self._policy.browser_allowed_domains,
            browser_allow_persistent_auth=self._policy.browser_allow_persistent_auth,
            browser_profile_root=self._policy.browser_profile_root,
            mail_web_provider=self._policy.mail_web_provider,
            weather_url_template=self._policy.weather_url_template,
            event_logger=self._execution_log_store,
            history=[
                {"role": turn.role, "content": turn.content, "name": turn.name}
                for turn in working_history
            ],
        )
        result = await asyncio.wait_for(
            tool.run(tool_call.arguments, context),
            timeout=min(tool.timeout_seconds, self._tool_timeout_seconds),
        )
        logger.info(
            "tool_execution_completed session_id=%s tool=%s",
            request.session_id,
            tool.name,
        )
        await self._execution_log_store.record(
            event_type="tool_execution_completed",
            message=f"tool={tool.name}",
            session_id=request.session_id,
        )
        return ToolResult(name=result.name, output=_shape_tool_output(result.output))


def _shape_tool_output(output: str) -> str:
    shaped = output
    for pattern in _SENSITIVE_PATTERNS:
        shaped = pattern.sub(r"\1[REDACTED]", shaped)
    if len(shaped) > MAX_TOOL_OUTPUT_CHARS:
        shaped = f"{shaped[:MAX_TOOL_OUTPUT_CHARS]}\n...[truncated]"
    return shaped
