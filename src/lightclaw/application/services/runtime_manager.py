from dataclasses import dataclass

from lightclaw.application.services.chat_service import ChatService
from lightclaw.application.services.job_service import JobService
from lightclaw.application.services.memory_extraction_service import MemoryExtractionService
from lightclaw.application.services.memory_service import MemoryService
from lightclaw.application.services.scheduler_service import SchedulerService
from lightclaw.application.services.skill_service import SkillService
from lightclaw.config.settings import AppSettings
from lightclaw.domain.providers.models import ProviderConfig
from lightclaw.domain.tools.base import ToolRegistry
from lightclaw.domain.tools.models import ExecutionPolicy
from lightclaw.infrastructure.providers.anthropic import AnthropicProvider
from lightclaw.infrastructure.providers.mock import MockProvider
from lightclaw.infrastructure.providers.openai_compatible import OpenAICompatibleProvider
from lightclaw.interfaces.feishu.sender import FeishuSender
from lightclaw.interfaces.feishu.service import FeishuService
from lightclaw.interfaces.telegram.sender import TelegramSender
from lightclaw.interfaces.telegram.service import TelegramService


@dataclass
class RuntimeServices:
    provider: object
    memory_extraction_service: MemoryExtractionService
    policy: ExecutionPolicy
    chat_service: ChatService
    telegram_sender: TelegramSender | None
    telegram_service: TelegramService
    feishu_sender: FeishuSender | None
    feishu_service: FeishuService
    job_service: JobService
    scheduler_service: SchedulerService


class RuntimeManager:
    def __init__(
        self,
        *,
        settings: AppSettings,
        memory_service: MemoryService,
        skill_service: SkillService,
        tool_registry: ToolRegistry,
        session_store,
        job_store,
        execution_log_store,
    ) -> None:
        self._settings = settings
        self._memory_service = memory_service
        self._skill_service = skill_service
        self._tool_registry = tool_registry
        self._session_store = session_store
        self._job_store = job_store
        self._execution_log_store = execution_log_store
        self._services = self._build_services(settings)

    @property
    def services(self) -> RuntimeServices:
        return self._services

    async def reload(self, settings: AppSettings) -> RuntimeServices:
        was_running = self._services.scheduler_service.status()["running"]
        if was_running:
            await self._services.scheduler_service.stop()
        self._settings = settings
        self._services = self._build_services(settings)
        if was_running:
            await self._services.scheduler_service.start()
        return self._services

    def _build_services(self, settings: AppSettings) -> RuntimeServices:
        provider = _build_provider(settings)
        memory_extraction_service = MemoryExtractionService(
            provider=provider,
            memory_service=self._memory_service,
        )
        policy = ExecutionPolicy(
            mode=settings.tool_policy,
            workspace_root=settings.workspace_root,
            allow_process_exec=settings.allow_process_exec,
            allow_network_access=settings.allow_network_access,
            allowed_commands=settings.allowed_commands,
        )
        chat_service = ChatService(
            provider=provider,
            session_store=self._session_store,
            memory_service=self._memory_service,
            memory_extraction_service=memory_extraction_service,
            skill_service=self._skill_service,
            tool_registry=self._tool_registry,
            policy=policy,
            execution_log_store=self._execution_log_store,
            max_loops=settings.max_agent_loops,
            provider_timeout_seconds=settings.provider_timeout_seconds,
            tool_timeout_seconds=settings.tool_timeout_seconds,
        )
        telegram_sender = (
            TelegramSender(settings.telegram_bot_token)
            if settings.telegram_bot_token
            else None
        )
        telegram_service = TelegramService(
            chat_service=chat_service,
            sender=telegram_sender,
        )
        feishu_sender = (
            FeishuSender(settings.feishu_app_id, settings.feishu_app_secret)
            if settings.feishu_app_id and settings.feishu_app_secret
            else None
        )
        feishu_service = FeishuService(
            chat_service=chat_service,
            sender=feishu_sender,
        )
        job_service = JobService(
            job_store=self._job_store,
            chat_service=chat_service,
            execution_log_store=self._execution_log_store,
            telegram_sender=telegram_sender,
            feishu_sender=feishu_sender,
        )
        scheduler_service = SchedulerService(
            job_service=job_service,
            execution_log_store=self._execution_log_store,
            poll_seconds=settings.scheduler_poll_seconds,
        )
        return RuntimeServices(
            provider=provider,
            memory_extraction_service=memory_extraction_service,
            policy=policy,
            chat_service=chat_service,
            telegram_sender=telegram_sender,
            telegram_service=telegram_service,
            feishu_sender=feishu_sender,
            feishu_service=feishu_service,
            job_service=job_service,
            scheduler_service=scheduler_service,
        )


def _build_provider(settings: AppSettings):
    if settings.provider_backend == "openai_compatible":
        return OpenAICompatibleProvider(
            ProviderConfig(
                backend=settings.provider_backend,
                model=settings.provider_model,
                base_url=settings.provider_base_url or "https://api.openai.com/v1",
                api_key=settings.provider_api_key,
                extra_headers=settings.provider_extra_headers,
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
