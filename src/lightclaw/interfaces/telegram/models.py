from pydantic import BaseModel, Field

from lightclaw.domain.channels.models import ChannelMessage


class TelegramWebhookPayload(BaseModel):
    update_id: int
    message: dict | None = None


class TelegramSendMessageResponse(BaseModel):
    ok: bool = True
    chat_id: str
    text: str


class TelegramNormalizedMessage(BaseModel):
    channel_message: ChannelMessage
    raw_update_id: int


class TelegramWebhookAck(BaseModel):
    ok: bool = True
    update_id: int
    session_id: str
    reply: str
    sent_to_telegram: bool = Field(default=False)
