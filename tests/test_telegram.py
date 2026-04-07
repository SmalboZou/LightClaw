import asyncio

import httpx
from fastapi.testclient import TestClient

from lightclaw.bootstrap import build_container
from lightclaw.config.settings import AppSettings
from lightclaw.interfaces.api.app import create_api
from lightclaw.interfaces.telegram.adapter import TelegramAdapter
from lightclaw.interfaces.telegram.models import TelegramWebhookPayload
from lightclaw.interfaces.telegram.sender import TelegramSender


def test_telegram_adapter_normalizes_text_message() -> None:
    adapter = TelegramAdapter()
    normalized = adapter.normalize_update(
        TelegramWebhookPayload(
            update_id=1001,
            message={
                "message_id": 10,
                "text": "hello telegram",
                "chat": {"id": 99, "type": "private"},
                "from": {"id": 42, "username": "tester"},
            },
        )
    )

    assert normalized is not None
    assert normalized.channel_message.channel_type == "telegram"
    assert normalized.channel_message.channel_user_id == "42"
    assert normalized.channel_message.channel_conversation_id == "99"
    assert normalized.channel_message.session_id == "telegram:99"
    assert normalized.channel_message.text == "hello telegram"


def test_telegram_webhook_processes_message_and_returns_ack() -> None:
    settings = AppSettings(storage_backend="memory")
    container = build_container(settings)
    client = TestClient(create_api(settings, container=container))

    response = client.post(
        "/telegram/webhook",
        json={
            "update_id": 2002,
            "message": {
                "message_id": 20,
                "text": "hello from webhook",
                "chat": {"id": 101, "type": "private"},
                "from": {"id": 55, "username": "webhook-user"},
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["update_id"] == 2002
    assert payload["session_id"] == "telegram:101"
    assert payload["sent_to_telegram"] is False
    assert "hello from webhook" in payload["reply"]


def test_telegram_webhook_rejects_invalid_secret() -> None:
    settings = AppSettings(
        storage_backend="memory",
        telegram_webhook_secret="expected-secret",
    )
    container = build_container(settings)
    client = TestClient(create_api(settings, container=container))

    response = client.post(
        "/telegram/webhook",
        json={"update_id": 3003, "message": None},
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
    )

    assert response.status_code == 403


def test_telegram_sender_calls_send_message_endpoint() -> None:
    async def _run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path.endswith("/sendMessage")
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

        sender = TelegramSender(
            bot_token="token",
            http_client=httpx.AsyncClient(
                transport=httpx.MockTransport(handler),
                base_url="https://api.telegram.org/bottoken",
            ),
        )
        response = await sender.send_message(chat_id="123", text="hello outbound")
        assert response.ok is True
        assert response.chat_id == "123"
        assert response.text == "hello outbound"

    asyncio.run(_run())
