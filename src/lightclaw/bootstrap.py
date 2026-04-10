from lightclaw.application.services.console_auth_service import ConsoleAuthService
from lightclaw.application.services.console_ownership_service import ConsoleOwnershipService
from lightclaw.application.services.config_service import ConfigService
from lightclaw.application.services.memory_service import MemoryService
from lightclaw.application.services.runtime_manager import RuntimeManager
from lightclaw.application.services.skill_service import SkillService
from lightclaw.config.settings import AppSettings
from lightclaw.domain.tools.base import CompositeToolRegistry
from lightclaw.infrastructure.jobs.in_memory import InMemoryJobStore
from lightclaw.infrastructure.jobs.sqlalchemy_store import SqlAlchemyJobStore
from lightclaw.infrastructure.logs.in_memory import InMemoryExecutionLogStore
from lightclaw.infrastructure.logs.sqlalchemy_store import SqlAlchemyExecutionLogStore
from lightclaw.infrastructure.mcp.filesystem_client import FilesystemMCPClient
from lightclaw.infrastructure.mcp.tool_registry import MCPToolRegistry
from lightclaw.infrastructure.skills.filesystem_registry import FilesystemSkillRegistry
from lightclaw.infrastructure.memory.in_memory import InMemoryMemoryStore
from lightclaw.infrastructure.memory.sqlalchemy_store import SqlAlchemyMemoryStore
from lightclaw.infrastructure.browser.service import build_browser_service
from lightclaw.infrastructure.persistence.database import create_session_factory
from lightclaw.infrastructure.sessions.in_memory import InMemorySessionStore
from lightclaw.infrastructure.sessions.sqlalchemy_store import SqlAlchemySessionStore
from lightclaw.infrastructure.tools.registry import InMemoryToolRegistry


class ApplicationContainer:
    """Simple dependency container for the first project iteration."""

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        metadata_root = settings.workspace_root / ".lightclaw"
        self._metadata_root = metadata_root
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
        self.config_service = ConfigService(
            settings.workspace_root / ".env",
            settings,
            self.db_session_factory,
        )
        self.console_auth_service = ConsoleAuthService(
            metadata_root / "console_users.json",
            settings,
            self.db_session_factory,
        )
        self.console_ownership_service = ConsoleOwnershipService(
            metadata_root / "console_ownership.json",
            self.db_session_factory,
        )
        self.browser_service = build_browser_service(settings.browser_backend)
        local_tool_registry = InMemoryToolRegistry(browser_service=self.browser_service)
        self.mcp_client = FilesystemMCPClient(settings.mcp_servers_root)
        self.mcp_tool_registry = MCPToolRegistry(self.mcp_client)
        self.tool_registry = CompositeToolRegistry(
            [local_tool_registry, self.mcp_tool_registry]
        )
        self.skill_registry = FilesystemSkillRegistry(settings.skills_root)
        self.skill_service = SkillService(self.skill_registry)
        self.memory_service = MemoryService(self.memory_store)
        self.runtime_manager = RuntimeManager(
            settings=settings,
            memory_service=self.memory_service,
            skill_service=self.skill_service,
            tool_registry=self.tool_registry,
            session_store=self.session_store,
            job_store=self.job_store,
            execution_log_store=self.execution_log_store,
        )
        self._apply_runtime_services()
        self.config_service.record_runtime_applied(settings, reason="startup")

    async def reload_runtime(self, settings: AppSettings) -> None:
        self.settings = settings
        self.config_service = ConfigService(
            settings.workspace_root / ".env",
            settings,
            self.db_session_factory,
        )
        self.console_auth_service.update_settings(settings)
        await self.runtime_manager.reload(settings)
        self._apply_runtime_services()
        self.config_service.record_runtime_applied(settings, reason="hot_reload")

    def _apply_runtime_services(self) -> None:
        services = self.runtime_manager.services
        self.provider = services.provider
        self.memory_extraction_service = services.memory_extraction_service
        self.policy = services.policy
        self.chat_service = services.chat_service
        self.telegram_sender = services.telegram_sender
        self.telegram_service = services.telegram_service
        self.feishu_sender = services.feishu_sender
        self.feishu_service = services.feishu_service
        self.job_service = services.job_service
        self.scheduler_service = services.scheduler_service


def build_container(settings: AppSettings | None = None) -> ApplicationContainer:
    return ApplicationContainer(settings or AppSettings())
