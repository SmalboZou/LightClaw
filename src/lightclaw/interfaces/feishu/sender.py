import json
from datetime import UTC, datetime, timedelta

import httpx

from lightclaw.domain.errors import ProviderRequestError
from lightclaw.interfaces.feishu.models import FeishuSendMessageResponse


class FeishuSender:
    def __init__(
        self,
        app_id: str,
        app_secret: str,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._app_id = app_id
        self._app_secret = app_secret
        self._http_client = http_client or httpx.AsyncClient(
            base_url="https://open.feishu.cn",
            timeout=20.0,
        )
        self._owns_client = http_client is None
        self._tenant_access_token: str | None = None
        self._tenant_access_token_expires_at: datetime | None = None

    async def send_message(
        self,
        receive_id: str,
        text: str,
        *,
        receive_id_type: str = "chat_id",
    ) -> FeishuSendMessageResponse:
        token = await self._get_tenant_access_token()
        try:
            response = await self._http_client.post(
                "/open-apis/im/v1/messages",
                params={"receive_id_type": receive_id_type},
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "receive_id": receive_id,
                    "msg_type": "text",
                    "content": json.dumps({"text": text}, ensure_ascii=False),
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderRequestError(f"Feishu send message failed: {exc}") from exc

        payload = response.json()
        if int(payload.get("code", 0)) != 0:
            raise ProviderRequestError(
                f"Feishu send message failed: {payload.get('msg', 'unknown error')}"
            )

        data = payload.get("data") or {}
        return FeishuSendMessageResponse(
            ok=True,
            receive_id=receive_id,
            receive_id_type=receive_id_type,
            text=text,
            message_id=data.get("message_id"),
        )

    async def _get_tenant_access_token(self) -> str:
        now = datetime.now(UTC)
        if (
            self._tenant_access_token is not None
            and self._tenant_access_token_expires_at is not None
            and now < self._tenant_access_token_expires_at
        ):
            return self._tenant_access_token

        try:
            response = await self._http_client.post(
                "/open-apis/auth/v3/tenant_access_token/internal",
                json={
                    "app_id": self._app_id,
                    "app_secret": self._app_secret,
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderRequestError(f"Feishu tenant access token request failed: {exc}") from exc

        payload = response.json()
        if int(payload.get("code", 0)) != 0 or "tenant_access_token" not in payload:
            raise ProviderRequestError(
                f"Feishu tenant access token request failed: {payload.get('msg', 'unknown error')}"
            )

        expires_in = int(payload.get("expire", 7200))
        self._tenant_access_token = str(payload["tenant_access_token"])
        self._tenant_access_token_expires_at = now + timedelta(
            seconds=max(60, expires_in - 60)
        )
        return self._tenant_access_token

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http_client.aclose()
