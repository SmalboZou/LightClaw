import httpx

from lightclaw.domain.errors import ProviderRequestError
from lightclaw.interfaces.telegram.models import TelegramSendMessageResponse


class TelegramSender:
    def __init__(
        self,
        bot_token: str,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._bot_token = bot_token
        self._http_client = http_client or httpx.AsyncClient(
            base_url=f"https://api.telegram.org/bot{bot_token}",
            timeout=20.0,
        )
        self._owns_client = http_client is None

    async def send_message(self, chat_id: str, text: str) -> TelegramSendMessageResponse:
        try:
            response = await self._http_client.post(
                "/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderRequestError(f"Telegram sendMessage failed: {exc}") from exc

        payload = response.json()
        return TelegramSendMessageResponse(ok=bool(payload.get("ok", True)), chat_id=chat_id, text=text)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http_client.aclose()
