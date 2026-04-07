from pydantic import BaseModel, Field

from lightclaw.domain.agent.models import ToolResult


class HealthResponse(BaseModel):
    status: str
    app: str


class ErrorResponse(BaseModel):
    error_code: str
    message: str


class ChatPayload(BaseModel):
    session_id: str = Field(default="default-session")
    user_id: str = Field(default="api-user")
    message: str = Field(min_length=1)
    channel: str = Field(default="api")
    skills: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    tool_results: list[ToolResult] = Field(default_factory=list)


class SkillResponse(BaseModel):
    skill_id: str
    name: str
    description: str
    tools: list[str] = Field(default_factory=list)
