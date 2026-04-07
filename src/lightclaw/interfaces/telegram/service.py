from lightclaw.application.services.chat_service import ChatService
from lightclaw.domain.agent.models import AgentRequest
from lightclaw.interfaces.telegram.adapter import TelegramAdapter
from lightclaw.interfaces.telegram.models import (
    TelegramWebhookAck,
    TelegramWebhookPayload,
)
from lightclaw.interfaces.telegram.sender import TelegramSender


class TelegramService:
    def __init__(
        self,
        chat_service: ChatService,
        adapter: TelegramAdapter | None = None,
        sender: TelegramSender | None = None,
    ) -> None:
        self._chat_service = chat_service
        self._adapter = adapter or TelegramAdapter()
        self._sender = sender

    async def handle_webhook(self, payload: TelegramWebhookPayload) -> TelegramWebhookAck:
        normalized = self._adapter.normalize_update(payload)
        if normalized is None:
            return TelegramWebhookAck(
                update_id=payload.update_id,
                session_id="ignored",
                reply="ignored",
                sent_to_telegram=False,
            )

        channel_message = normalized.channel_message
        response = await self._chat_service.chat(
            AgentRequest(
                session_id=channel_message.session_id,
                user_id=channel_message.channel_user_id,
                message=channel_message.text,
                channel=channel_message.channel_type,
            )
        )

        sent = False
        if self._sender is not None:
            await self._sender.send_message(
                chat_id=channel_message.channel_conversation_id,
                text=response.reply,
            )
            sent = True

        return TelegramWebhookAck(
            update_id=payload.update_id,
            session_id=channel_message.session_id,
            reply=response.reply,
            sent_to_telegram=sent,
        )
