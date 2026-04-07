from datetime import datetime

from pydantic import BaseModel, Field

from lightclaw.domain.agent.models import AgentTurn
from lightclaw.domain.tools.models import ToolDefinition


class ConsoleConfigResponse(BaseModel):
    provider_backend: str
    provider_model: str
    provider_base_url: str | None = None
    provider_extra_headers_json: str = ""
    provider_api_key_masked: str | None = None
    has_provider_api_key: bool
    storage_backend: str
    tool_policy: str
    allow_process_exec: bool
    allow_network_access: bool
    workspace_root: str
    skills_root: str
    mcp_servers_root: str
    console_admin_username: str | None = None
    requires_restart: bool = False


class ConsoleConfigUpdatePayload(BaseModel):
    provider_backend: str
    provider_model: str
    provider_base_url: str | None = None
    provider_extra_headers_json: str = ""
    provider_api_key: str | None = None
    storage_backend: str = "sqlite"
    tool_policy: str = "workspace_write"
    allow_process_exec: bool = False
    allow_network_access: bool = False
    console_admin_username: str | None = None
    console_admin_password: str | None = None


class ConsoleConfigUpdateResponse(BaseModel):
    saved: bool
    requires_restart: bool
    updated_keys: list[str] = Field(default_factory=list)


class SessionSummaryResponse(BaseModel):
    session_id: str
    turn_count: int
    last_role: str | None = None
    preview: str
    updated_at: datetime


class SessionDetailResponse(BaseModel):
    session_id: str
    turns: list[AgentTurn] = Field(default_factory=list)


class ExecutionLogResponse(BaseModel):
    event_type: str
    message: str
    session_id: str
    created_at: str = ""


class ToolDefinitionResponse(BaseModel):
    name: str
    description: str
    required_scope: str
    timeout_seconds: float
    argument_schema: dict[str, object] = Field(default_factory=dict)
    audit_enabled: bool = True

    @classmethod
    def from_definition(cls, definition: ToolDefinition) -> "ToolDefinitionResponse":
        return cls(**definition.model_dump())


class ConsoleSystemStatusResponse(BaseModel):
    app_name: str
    env: str
    storage_backend: str
    provider_backend: str
    provider_model: str
    scheduler_running: bool
    scheduler_poll_seconds: int
    current_schema_version: str | None = None
    latest_schema_version: str | None = None
    pending_schema_versions: list[str] = Field(default_factory=list)


class ConsoleSetupStatusResponse(BaseModel):
    setup_required: bool
    has_users: bool
    has_provider_config: bool


class ConsoleBootstrapPayload(BaseModel):
    admin_username: str
    admin_password: str
    provider_backend: str
    provider_model: str
    provider_base_url: str | None = None
    provider_extra_headers_json: str = ""
    provider_api_key: str | None = None
    storage_backend: str = "sqlite"
    tool_policy: str = "workspace_write"
    allow_process_exec: bool = False
    allow_network_access: bool = False


class ConsoleAuthPayload(BaseModel):
    username: str
    password: str


class ConsoleUserResponse(BaseModel):
    username: str
    role: str
    created_at: str | None = None


class ConsoleAuthResponse(BaseModel):
    authenticated: bool
    user: ConsoleUserResponse | None = None


class ConsoleCreateUserPayload(BaseModel):
    username: str
    password: str
    role: str = "operator"


class ConsoleProviderTestPayload(BaseModel):
    provider_backend: str
    provider_model: str
    provider_base_url: str | None = None
    provider_extra_headers_json: str = ""
    provider_api_key: str | None = None


class ConsoleProviderTestResponse(BaseModel):
    ok: bool
    backend: str
    model: str | None = None
    message: str


class ConsoleChatPayload(BaseModel):
    session_id: str = "console-session"
    message: str
    skills: list[str] = Field(default_factory=list)
