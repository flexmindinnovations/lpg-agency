"""`WhatsAppSenderPort` over Meta's WhatsApp Cloud API (Graph API
`/{phone-number-id}/messages`).

Free-form text is allowed within 24 hours of the customer's last message,
which every reply this assistant sends is (it only ever answers). Proactive
messages outside that window need approved templates and are not sent here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from lpg.config.logging import get_logger

if TYPE_CHECKING:
    from lpg.config.settings import Settings

_logger = get_logger(__name__)

_GRAPH_BASE_URL = "https://graph.facebook.com"

#: WhatsApp's limit on a text message body.
MAX_BODY_LENGTH = 4096


class MetaWhatsAppCloudSender:
    def __init__(
        self,
        *,
        access_token: str,
        api_version: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._access_token = access_token
        self._api_version = api_version
        self._client = client or httpx.AsyncClient(timeout=15.0)

    async def send_text(self, *, phone_number_id: str, to: str, body: str) -> str | None:
        url = f"{_GRAPH_BASE_URL}/{self._api_version}/{phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to.lstrip("+"),
            "type": "text",
            "text": {"preview_url": False, "body": body[:MAX_BODY_LENGTH]},
        }
        try:
            response = await self._client.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {self._access_token}"},
            )
        except httpx.HTTPError as exc:
            _logger.warning("whatsapp_send_transport_error", error=str(exc))
            return None
        if response.status_code >= 400:
            _logger.warning(
                "whatsapp_send_rejected",
                status_code=response.status_code,
                body=response.text[:500],
            )
            return None
        messages = response.json().get("messages") or []
        message_id = messages[0].get("id") if messages else None
        return message_id if isinstance(message_id, str) else None

    async def aclose(self) -> None:
        await self._client.aclose()


class StubWhatsAppSender:
    """No access token configured: log the reply instead of sending it, the
    same fallback `StubPushChannel` gives push notifications."""

    async def send_text(self, *, phone_number_id: str, to: str, body: str) -> str | None:
        _logger.info(
            "stub_whatsapp_send",
            phone_number_id=phone_number_id,
            to_suffix=to[-4:],
            body_length=len(body),
        )
        return None


def build_whatsapp_sender(settings: Settings) -> MetaWhatsAppCloudSender | StubWhatsAppSender:
    if settings.whatsapp_access_token is None:
        return StubWhatsAppSender()
    return MetaWhatsAppCloudSender(
        access_token=settings.whatsapp_access_token.get_secret_value(),
        api_version=settings.whatsapp_graph_api_version,
    )
