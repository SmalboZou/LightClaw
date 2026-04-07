from typing import Any

from pydantic import BaseModel, Field

from lightclaw.domain.tools.models import ToolScope


class MCPToolSpec(BaseModel):
    server_id: str
    name: str
    description: str
    required_scope: ToolScope = "read_only"
    timeout_seconds: float = 10.0
    argument_schema: dict[str, Any] = Field(default_factory=dict)
    response_template: str | None = None
    static_output: str | None = None

    @property
    def exposed_name(self) -> str:
        return f"mcp.{self.server_id}.{self.name}"


class MCPCallResult(BaseModel):
    content: str
