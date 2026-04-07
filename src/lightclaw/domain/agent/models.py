from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    name: str
    output: str


class AgentTurn(BaseModel):
    role: str
    content: str
    name: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentRequest(BaseModel):
    session_id: str
    message: str
    user_id: str
    channel: str
    skills: list[str] = Field(default_factory=list)


class AgentResponse(BaseModel):
    session_id: str
    reply: str
    tool_results: list[ToolResult] = Field(default_factory=list)
