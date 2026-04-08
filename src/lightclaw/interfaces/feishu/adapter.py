import json
from datetime import UTC, datetime

from lightclaw.domain.channels.models import ChannelMessage
from lightclaw.interfaces.feishu.models import FeishuNormalizedMessage, FeishuWebhookPayload


class FeishuAdapter:
    """Normalize Feishu event callbacks into internal channel messages."""

    def normalize_event(self, payload: FeishuWebhookPayload) -> FeishuNormalizedMessage | None:
        header = payload.header or {}
        if header.get("event_type") != "im.message.receive_v1":
            return None

        event = payload.event or {}
        message = event.get("message") or {}
        if message.get("message_type") != "text":
            return None

        content = _extract_text(message.get("content"))
        if not content:
            return None

        sender = event.get("sender") or {}
        sender_id = sender.get("sender_id") or {}
        user_id = str(
            sender_id.get("open_id")
            or sender_id.get("user_id")
            or sender_id.get("union_id")
            or "unknown-user"
        )
        chat_id = str(message.get("chat_id") or "unknown-chat")
        message_id = str(message.get("message_id") or "unknown-message")
        session_id = f"feishu:{chat_id}"

        channel_message = ChannelMessage(
            message_id=message_id,
            channel_type="feishu",
            channel_user_id=user_id,
            channel_conversation_id=chat_id,
            session_id=session_id,
            text=content,
            metadata={
                "feishu_chat_type": message.get("chat_type"),
                "feishu_message_type": message.get("message_type"),
                "feishu_tenant_key": sender.get("tenant_key"),
                "feishu_sender_type": sender.get("sender_type"),
            },
            timestamp=datetime.now(UTC),
        )
        return FeishuNormalizedMessage(
            channel_message=channel_message,
            raw_event_type=str(header.get("event_type")),
            chat_id=chat_id,
            message_id=message_id,
        )


def _extract_text(raw_content: object) -> str | None:
    if not isinstance(raw_content, str) or not raw_content.strip():
        return None
    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    text = parsed.get("text")
    if not isinstance(text, str):
        return None
    normalized = text.strip()
    return normalized or None
