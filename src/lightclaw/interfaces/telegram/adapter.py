from datetime import UTC, datetime

from lightclaw.domain.channels.models import ChannelMessage
from lightclaw.interfaces.telegram.models import TelegramNormalizedMessage, TelegramWebhookPayload


class TelegramAdapter:
    """Normalize Telegram updates into internal channel messages."""

    def normalize_update(self, payload: TelegramWebhookPayload) -> TelegramNormalizedMessage | None:
        message = payload.message
        if message is None:
            return None

        text = message.get("text")
        if not isinstance(text, str) or not text.strip():
            return None

        telegram_message_id = str(message.get("message_id", payload.update_id))
        chat = message.get("chat") or {}
        user = message.get("from") or {}
        chat_id = str(chat.get("id", "unknown-chat"))
        user_id = str(user.get("id", "unknown-user"))
        session_id = f"telegram:{chat_id}"

        channel_message = ChannelMessage(
            message_id=telegram_message_id,
            channel_type="telegram",
            channel_user_id=user_id,
            channel_conversation_id=chat_id,
            session_id=session_id,
            text=text,
            metadata={
                "telegram_chat_type": chat.get("type"),
                "telegram_username": user.get("username"),
            },
            timestamp=datetime.now(UTC),
        )
        return TelegramNormalizedMessage(
            channel_message=channel_message,
            raw_update_id=payload.update_id,
        )
