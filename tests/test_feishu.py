import asyncio
import base64
import hashlib
import json
import os

import httpx
from fastapi.testclient import TestClient

from lightclaw.bootstrap import build_container
from lightclaw.config.settings import AppSettings
from lightclaw.interfaces.api.app import create_api
from lightclaw.interfaces.feishu.adapter import FeishuAdapter
from lightclaw.interfaces.feishu.models import FeishuWebhookPayload
from lightclaw.interfaces.feishu.security import calculate_signature
from lightclaw.interfaces.feishu.sender import FeishuSender

try:
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
except ModuleNotFoundError:  # pragma: no cover - handled in runtime setup
    default_backend = None
    padding = None
    Cipher = None
    algorithms = None
    modes = None


def test_feishu_adapter_normalizes_text_message() -> None:
    adapter = FeishuAdapter()
    normalized = adapter.normalize_event(
        FeishuWebhookPayload(
            schema="2.0",
            header={"event_type": "im.message.receive_v1"},
            event={
                "sender": {
                    "sender_id": {"open_id": "ou_test"},
                    "sender_type": "user",
                    "tenant_key": "tenant-test",
                },
                "message": {
                    "message_id": "om_123",
                    "chat_id": "oc_456",
                    "chat_type": "p2p",
                    "message_type": "text",
                    "content": "{\"text\":\"hello feishu\"}",
                },
            },
        )
    )

    assert normalized is not None
    assert normalized.channel_message.channel_type == "feishu"
    assert normalized.channel_message.channel_user_id == "ou_test"
    assert normalized.channel_message.channel_conversation_id == "oc_456"
    assert normalized.channel_message.session_id == "feishu:oc_456"
    assert normalized.channel_message.text == "hello feishu"


def test_feishu_webhook_processes_message_and_returns_ack() -> None:
    settings = AppSettings(storage_backend="memory", provider_backend="mock")
    container = build_container(settings)
    client = TestClient(create_api(settings, container=container))

    response = client.post(
        "/feishu/webhook",
        json={
            "schema": "2.0",
            "header": {"event_type": "im.message.receive_v1"},
            "event": {
                "sender": {
                    "sender_id": {"open_id": "ou_webhook"},
                    "sender_type": "user",
                },
                "message": {
                    "message_id": "om_2002",
                    "chat_id": "oc_101",
                    "chat_type": "p2p",
                    "message_type": "text",
                    "content": "{\"text\":\"hello from feishu webhook\"}",
                },
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["event_type"] == "im.message.receive_v1"
    assert payload["session_id"] == "feishu:oc_101"
    assert payload["sent_to_feishu"] is False
    assert "hello from feishu webhook" in payload["reply"]


def test_feishu_webhook_url_verification_returns_challenge() -> None:
    settings = AppSettings(storage_backend="memory", provider_backend="mock")
    client = TestClient(create_api(settings, container=build_container(settings)))

    response = client.post(
        "/feishu/webhook",
        json={
            "type": "url_verification",
            "challenge": "verify-me",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"challenge": "verify-me"}


def test_feishu_webhook_rejects_invalid_verification_token() -> None:
    settings = AppSettings(
        storage_backend="memory",
        provider_backend="mock",
        feishu_verification_token="expected-token",
    )
    client = TestClient(create_api(settings, container=build_container(settings)))

    response = client.post(
        "/feishu/webhook",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "token": "wrong-token",
            },
            "event": None,
        },
    )

    assert response.status_code == 403


def test_feishu_sender_requests_token_and_sends_message() -> None:
    async def _run() -> None:
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request.url.path)
            if request.url.path.endswith("/tenant_access_token/internal"):
                return httpx.Response(
                    200,
                    json={
                        "code": 0,
                        "msg": "success",
                        "tenant_access_token": "tenant-token",
                        "expire": 7200,
                    },
                )
            assert request.url.path.endswith("/im/v1/messages")
            assert request.url.params["receive_id_type"] == "chat_id"
            assert request.headers["Authorization"] == "Bearer tenant-token"
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "msg": "success",
                    "data": {"message_id": "om_sent"},
                },
            )

        sender = FeishuSender(
            app_id="cli_aid",
            app_secret="secret",
            http_client=httpx.AsyncClient(
                transport=httpx.MockTransport(handler),
                base_url="https://open.feishu.cn",
            ),
        )
        response = await sender.send_message(receive_id="oc_123", text="hello outbound")
        assert response.ok is True
        assert response.receive_id == "oc_123"
        assert response.receive_id_type == "chat_id"
        assert response.text == "hello outbound"
        assert response.message_id == "om_sent"
        assert calls.count("/open-apis/auth/v3/tenant_access_token/internal") == 1
        assert calls.count("/open-apis/im/v1/messages") == 1

    asyncio.run(_run())


def test_feishu_webhook_decrypts_encrypted_event_and_verifies_signature() -> None:
    if Cipher is None:
        return

    settings = AppSettings(
        storage_backend="memory",
        provider_backend="mock",
        feishu_verification_token="verify-token",
        feishu_encrypt_key="encrypt-key",
    )
    client = TestClient(create_api(settings, container=build_container(settings)))
    decrypted_body = {
        "schema": "2.0",
        "header": {
            "event_type": "im.message.receive_v1",
            "token": "verify-token",
        },
        "event": {
            "sender": {
                "sender_id": {"open_id": "ou_secure"},
                "sender_type": "user",
            },
            "message": {
                "message_id": "om_secure",
                "chat_id": "oc_secure",
                "chat_type": "p2p",
                "message_type": "text",
                "content": "{\"text\":\"secure hello\"}",
            },
        },
    }
    encrypted = _encrypt_feishu_payload(json.dumps(decrypted_body), "encrypt-key")
    request_body = json.dumps({"encrypt": encrypted}, separators=(",", ":")).encode("utf-8")
    timestamp = "1700000000"
    nonce = "nonce-value"
    signature = calculate_signature(timestamp, nonce, "encrypt-key", request_body)

    response = client.post(
        "/feishu/webhook",
        content=request_body,
        headers={
            "Content-Type": "application/json",
            "X-Lark-Request-Timestamp": timestamp,
            "X-Lark-Request-Nonce": nonce,
            "X-Lark-Signature": signature,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "feishu:oc_secure"
    assert "secure hello" in payload["reply"]


def _encrypt_feishu_payload(plaintext: str, encrypt_key: str) -> str:
    assert Cipher is not None
    key = hashlib.sha256(encrypt_key.encode("utf-8")).digest()
    iv = bytes(range(16))
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded = padder.update(plaintext.encode("utf-8")) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(iv + ciphertext).decode("utf-8")
