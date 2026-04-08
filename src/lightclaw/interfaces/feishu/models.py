from pydantic import BaseModel, ConfigDict, Field

from lightclaw.domain.channels.models import ChannelMessage


class FeishuWebhookPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_schema: str | None = Field(default=None, alias="schema")
    header: dict | None = None
    event: dict | None = None
    encrypt: str | None = None
    challenge: str | None = None
    token: str | None = None
    type: str | None = None


class FeishuSendMessageResponse(BaseModel):
    ok: bool = True
    receive_id: str
    receive_id_type: str
    text: str
    message_id: str | None = None


class FeishuNormalizedMessage(BaseModel):
    channel_message: ChannelMessage
    raw_event_type: str | None = None
    chat_id: str
    message_id: str


class FeishuChallengeResponse(BaseModel):
    challenge: str


class FeishuWebhookAck(BaseModel):
    ok: bool = True
    event_type: str
    session_id: str
    reply: str
    sent_to_feishu: bool = Field(default=False)
