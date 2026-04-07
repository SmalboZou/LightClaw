from datetime import UTC, datetime

from pydantic import BaseModel, Field


class SessionSummary(BaseModel):
    session_id: str
    turn_count: int = 0
    last_role: str | None = None
    preview: str = ""
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
