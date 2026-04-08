from lightclaw.application.services.chat_service import ChatService
from lightclaw.domain.agent.models import AgentRequest
from lightclaw.interfaces.feishu.adapter import FeishuAdapter
from lightclaw.interfaces.feishu.models import (
    FeishuChallengeResponse,
    FeishuWebhookAck,
    FeishuWebhookPayload,
)
from lightclaw.interfaces.feishu.sender import FeishuSender


class FeishuService:
    def __init__(
        self,
        chat_service: ChatService,
        adapter: FeishuAdapter | None = None,
        sender: FeishuSender | None = None,
    ) -> None:
        self._chat_service = chat_service
        self._adapter = adapter or FeishuAdapter()
        self._sender = sender

    async def handle_webhook(
        self,
        payload: FeishuWebhookPayload,
    ) -> FeishuWebhookAck | FeishuChallengeResponse:
        if payload.type == "url_verification" and payload.challenge:
            return FeishuChallengeResponse(challenge=payload.challenge)

        normalized = self._adapter.normalize_event(payload)
        if normalized is None:
            return FeishuWebhookAck(
                event_type=str((payload.header or {}).get("event_type") or "ignored"),
                session_id="ignored",
                reply="ignored",
                sent_to_feishu=False,
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
                receive_id=channel_message.channel_conversation_id,
                text=response.reply,
                receive_id_type="chat_id",
            )
            sent = True

        return FeishuWebhookAck(
            event_type=normalized.raw_event_type or "unknown",
            session_id=channel_message.session_id,
            reply=response.reply,
            sent_to_feishu=sent,
        )
