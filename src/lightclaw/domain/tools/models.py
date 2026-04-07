from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


ToolScope = Literal["read_only", "workspace_write", "process_exec", "network_access"]


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

    def allows(self, required_scope: ToolScope) -> bool:
        if required_scope == "read_only":
            return True
        if required_scope == "workspace_write":
            return self.mode == "workspace_write"
        if required_scope == "process_exec":
            return self.allow_process_exec
        if required_scope == "network_access":
            return self.allow_network_access
        return False

    def is_command_allowed(self, command: str) -> bool:
        if not self.allow_process_exec:
            return False
        if not self.allowed_commands:
            return True
        return command in self.allowed_commands


class ToolExecutionContext(BaseModel):
    session_id: str
    user_id: str
    workspace_root: Path
    allow_process_exec: bool = False
    allow_network_access: bool = False
    allowed_commands: list[str] = Field(default_factory=list)
    history: list[dict[str, Any]] = Field(default_factory=list)
