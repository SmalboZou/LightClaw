from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ToolScope = Literal[
    "read_only",
    "workspace_write",
    "process_exec",
    "network_access",
    "browser_read",
    "browser_write",
    "browser_auth",
]


class ToolDefinition(BaseModel):
    name: str
    description: str
    required_scope: ToolScope
    timeout_seconds: float
    argument_schema: dict[str, Any] = Field(default_factory=dict)
    audit_enabled: bool = True


class ExecutionPolicy(BaseModel):
    mode: ToolScope = "workspace_write"
    workspace_root: Path
    allow_process_exec: bool = False
    allow_network_access: bool = False
    allowed_commands: list[str] = Field(default_factory=list)
    browser_enabled: bool = False
    browser_backend: str = "mock"
    browser_headless: bool = True
    browser_allowed_domains: list[str] = Field(default_factory=list)
    browser_allow_persistent_auth: bool = False
    browser_profile_root: Path | None = None
    mail_web_provider: str = "gmail"
    weather_url_template: str = "https://wttr.in/{location}"

    def allows(self, required_scope: ToolScope) -> bool:
        if required_scope == "read_only":
            return True
        if required_scope == "workspace_write":
            return self.mode == "workspace_write"
        if required_scope == "process_exec":
            return self.allow_process_exec
        if required_scope == "network_access":
            return self.allow_network_access
        if required_scope == "browser_read":
            return self.browser_enabled
        if required_scope == "browser_write":
            return self.browser_enabled
        if required_scope == "browser_auth":
            return self.browser_enabled and self.browser_allow_persistent_auth
        return False

    def is_command_allowed(self, command: str) -> bool:
        if not self.allow_process_exec:
            return False
        if not self.allowed_commands:
            return True
        return command in self.allowed_commands


class ToolExecutionContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    session_id: str
    user_id: str
    workspace_root: Path
    allow_process_exec: bool = False
    allow_network_access: bool = False
    allowed_commands: list[str] = Field(default_factory=list)
    browser_enabled: bool = False
    browser_backend: str = "mock"
    browser_headless: bool = True
    browser_allowed_domains: list[str] = Field(default_factory=list)
    browser_allow_persistent_auth: bool = False
    browser_profile_root: Path | None = None
    mail_web_provider: str = "gmail"
    weather_url_template: str = "https://wttr.in/{location}"
    browser_service: Any | None = None
    event_logger: Any | None = None
    history: list[dict[str, Any]] = Field(default_factory=list)
