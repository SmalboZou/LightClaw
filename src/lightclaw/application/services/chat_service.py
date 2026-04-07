from lightclaw.domain.agent.models import AgentRequest, AgentResponse
from lightclaw.domain.agent.runtime import AgentRuntime
from lightclaw.domain.logs.base import ExecutionLogStore
from lightclaw.domain.providers.base import ModelProvider
from lightclaw.domain.sessions.base import SessionStore
from lightclaw.domain.tools.base import ToolRegistry
from lightclaw.domain.tools.models import ExecutionPolicy
from lightclaw.application.services.memory_extraction_service import MemoryExtractionService
from lightclaw.application.services.memory_service import MemoryService
from lightclaw.application.services.skill_service import SkillService


class ChatService:
    def __init__(
        self,
        provider: ModelProvider,
        session_store: SessionStore,
        memory_service: MemoryService,
        memory_extraction_service: MemoryExtractionService,
        skill_service: SkillService,
        tool_registry: ToolRegistry,
        policy: ExecutionPolicy,
        execution_log_store: ExecutionLogStore,
        max_loops: int = 4,
        provider_timeout_seconds: float = 15.0,
        tool_timeout_seconds: float = 10.0,
    ) -> None:
        self._runtime = AgentRuntime(
            provider=provider,
            session_store=session_store,
            memory_service=memory_service,
            tool_registry=tool_registry,
            policy=policy,
            execution_log_store=execution_log_store,
            max_loops=max_loops,
            provider_timeout_seconds=provider_timeout_seconds,
            tool_timeout_seconds=tool_timeout_seconds,
        )
        self._memory_extraction_service = memory_extraction_service
        self._skill_service = skill_service
        self._tool_registry = tool_registry

    async def chat(self, request: AgentRequest) -> AgentResponse:
        skill_context = await self._skill_service.resolve_context(request.skills)
        tool_registry = await self._skill_service.apply_tool_context(
            self._tool_registry,
            skill_context,
        )
        response = await self._runtime.run(
            request,
            tool_registry=tool_registry,
            instructions=skill_context.prompt_fragments,
        )
        await self._memory_extraction_service.extract_and_remember(
            user_id=request.user_id,
            session_id=request.session_id,
            user_message=request.message,
            assistant_reply=response.reply,
        )
        return response
