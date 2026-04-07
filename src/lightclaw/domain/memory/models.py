from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


MemoryKind = Literal["profile", "preference", "project_fact", "task_rule", "reminder", "legacy"]
MemoryScope = Literal["user", "session", "global"]


class MemoryRecord(BaseModel):
    user_id: str
    content: str
    kind: MemoryKind = "project_fact"
    scope: MemoryScope = "user"
    session_id: str | None = None
    source: str = "manual"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_context_line(self) -> str:
        return f"[{self.kind}] {self.content}"


class MemoryWriteRequest(BaseModel):
    user_id: str
    content: str
    kind: MemoryKind = "project_fact"
    scope: MemoryScope = "user"
    session_id: str | None = None
    source: str = "manual"


class MemoryWritePolicy(BaseModel):
    max_content_length: int = 500
    allowed_kinds: list[MemoryKind] = Field(
        default_factory=lambda: ["profile", "preference", "project_fact", "task_rule", "reminder"]
    )

    def allows(self, request: MemoryWriteRequest) -> bool:
        if not request.content.strip():
            return False
        if len(request.content) > self.max_content_length:
            return False
        return request.kind in self.allowed_kinds
