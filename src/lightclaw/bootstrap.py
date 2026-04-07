from lightclaw.application.services.chat_service import ChatService
from lightclaw.application.services.job_service import JobService
from lightclaw.application.services.memory_extraction_service import MemoryExtractionService
from lightclaw.application.services.memory_service import MemoryService
from lightclaw.application.services.scheduler_service import SchedulerService
from lightclaw.application.services.skill_service import SkillService
from lightclaw.config.settings import AppSettings
from lightclaw.domain.providers.models import ProviderConfig
from lightclaw.domain.tools.base import CompositeToolRegistry
from lightclaw.infrastructure.jobs.in_memory import InMemoryJobStore
from lightclaw.infrastructure.jobs.sqlalchemy_store import SqlAlchemyJobStore
from lightclaw.infrastructure.logs.in_memory import InMemoryExecutionLogStore
from lightclaw.infrastructure.logs.sqlalchemy_store import SqlAlchemyExecutionLogStore
from lightclaw.infrastructure.mcp.filesystem_client import FilesystemMCPClient
from lightclaw.infrastructure.mcp.tool_registry import MCPToolRegistry
from lightclaw.infrastructure.skills.filesystem_registry import FilesystemSkillRegistry
from lightclaw.domain.tools.models import ExecutionPolicy
from lightclaw.infrastructure.memory.in_memory import InMemoryMemoryStore
from lightclaw.infrastructure.memory.sqlalchemy_store import SqlAlchemyMemoryStore
from lightclaw.infrastructure.persistence.database import create_session_factory
from lightclaw.infrastructure.providers.anthropic import AnthropicProvider
from lightclaw.infrastructure.providers.mock import MockProvider
from lightclaw.infrastructure.providers.openai_compatible import OpenAICompatibleProvider
from lightclaw.infrastructure.sessions.in_memory import InMemorySessionStore
from lightclaw.infrastructure.sessions.sqlalchemy_store import SqlAlchemySessionStore
from lightclaw.infrastructure.tools.registry import InMemoryToolRegistry
from lightclaw.interfaces.telegram.sender import TelegramSender
from lightclaw.interfaces.telegram.service import TelegramService


class ApplicationContainer:
    """Simple dependency container for the first project iteration."""

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.provider = _build_provider(settings)
        self.db_session_factory = None
        if settings.storage_backend == "sqlite":
            self.db_session_factory = create_session_factory(settings.database_url)
            self.session_store = SqlAlchemySessionStore(self.db_session_factory)
            self.memory_store = SqlAlchemyMemoryStore(self.db_session_factory)
            self.execution_log_store = SqlAlchemyExecutionLogStore(self.db_session_factory)
            self.job_store = SqlAlchemyJobStore(self.db_session_factory)
        else:
            self.session_store = InMemorySessionStore()
            self.memory_store = InMemoryMemoryStore()
            self.execution_log_store = InMemoryExecutionLogStore()
            self.job_store = InMemoryJobStore()
        local_tool_registry = InMemoryToolRegistry()
        self.mcp_client = FilesystemMCPClient(settings.mcp_servers_root)
        self.mcp_tool_registry = MCPToolRegistry(self.mcp_client)
        self.tool_registry = CompositeToolRegistry(
            [local_tool_registry, self.mcp_tool_registry]
        )
        self.skill_registry = FilesystemSkillRegistry(settings.skills_root)
        self.skill_service = SkillService(self.skill_registry)
        self.memory_service = MemoryService(self.memory_store)
        self.memory_extraction_service = MemoryExtractionService(
            provider=self.provider,
            memory_service=self.memory_service,
        )
        self.policy = ExecutionPolicy(
            mode=settings.tool_policy,
            workspace_root=settings.workspace_root,
            allow_process_exec=settings.allow_process_exec,
            allow_network_access=settings.allow_network_access,
            allowed_commands=settings.allowed_commands,
        )
        self.chat_service = ChatService(
            provider=self.provider,
            session_store=self.session_store,
            memory_service=self.memory_service,
            memory_extraction_service=self.memory_extraction_service,
            skill_service=self.skill_service,
            tool_registry=self.tool_registry,
            policy=self.policy,
            execution_log_store=self.execution_log_store,
            max_loops=settings.max_agent_loops,
            provider_timeout_seconds=settings.provider_timeout_seconds,
            tool_timeout_seconds=settings.tool_timeout_seconds,
        )
        self.telegram_sender = (
            TelegramSender(settings.telegram_bot_token)
            if settings.telegram_bot_token
            else None
        )
        self.telegram_service = TelegramService(
            chat_service=self.chat_service,
            sender=self.telegram_sender,
        )
        self.job_service = JobService(
            job_store=self.job_store,
            chat_service=self.chat_service,
            execution_log_store=self.execution_log_store,
            telegram_sender=self.telegram_sender,
        )
        self.scheduler_service = SchedulerService(
            job_service=self.job_service,
            execution_log_store=self.execution_log_store,
            poll_seconds=settings.scheduler_poll_seconds,
        )


def build_container(settings: AppSettings | None = None) -> ApplicationContainer:
    return ApplicationContainer(settings or AppSettings())


def _build_provider(settings: AppSettings):
    if settings.provider_backend == "openai_compatible":
        return OpenAICompatibleProvider(
            ProviderConfig(
                backend=settings.provider_backend,
                model=settings.provider_model,
                base_url=settings.provider_base_url or "https://api.openai.com/v1",
                api_key=settings.provider_api_key,
            )
        )
    if settings.provider_backend == "anthropic":
        return AnthropicProvider(
            ProviderConfig(
                backend=settings.provider_backend,
                model=settings.provider_model,
                base_url=settings.provider_base_url or "https://api.anthropic.com",
                api_key=settings.provider_api_key,
            )
        )
    return MockProvider()
