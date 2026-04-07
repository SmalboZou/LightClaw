from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class ChannelMessage(BaseModel):
    message_id: str
    channel_type: str
    channel_user_id: str
    channel_conversation_id: str
    session_id: str
    text: str
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
