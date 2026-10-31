"""Razorpay adapter for `PaymentGateway` (ADR-053).

Talks to Razorpay's Payment Links API over plain HTTPS (`httpx`) rather than
the `razorpay` SDK: the SDK is synchronous, and three endpoints plus an HMAC
check do not justify a blocking dependency in an async service.

- Create: `POST /v1/payment_links`
- Fetch:  `GET /v1/payment_links/{id}`
- Webhooks: `payment_link.paid`, `payment_link.expired`,
  `payment_link.cancelled`, signed with HMAC-SHA256 of the raw body using
  the webhook secret (`X-Razorpay-Signature`).

Test mode and live mode differ only in the key pair (`rzp_test_…` vs
`rzp_live_…`), so the same code runs against both.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import httpx

from lpg.application.accounting.payment_gateway import (
    InvalidWebhookSignatureError,
    PaymentGatewayError,
    PaymentLink,
    PaymentLinkStatus,
)
from lpg.config.logging import get_logger

if TYPE_CHECKING:
    from decimal import Decimal

    from lpg.application.accounting.payment_gateway import PaymentLinkRequest

_logger = get_logger(__name__)

# Razorpay's link statuses, folded onto `OnlinePayment`'s. `partially_paid`
# cannot happen (links are created with `accept_partial: false`) but is
# mapped to "still open" rather than trusted as paid if it ever appears.
_LINK_STATUS_MAP: dict[str, str] = {
    "created": "created",
    "partially_paid": "created",
    "paid": "paid",
    "expired": "expired",
    "cancelled": "cancelled",
}
_HANDLED_EVENTS: frozenset[str] = frozenset(
    {"payment_link.paid", "payment_link.expired", "payment_link.cancelled"}
)


def to_paise(amount: Decimal) -> int:
    return int((amount * 100).to_integral_value())


def _timestamp(value: object) -> datetime | None:
    if isinstance(value, int | float) and value > 0:
        return datetime.fromtimestamp(value, tz=UTC)
    return None


def _notes(entity: dict[str, Any]) -> dict[str, str]:
    raw = entity.get("notes")
    # Razorpay serialises empty notes as `[]`, not `{}`.
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items()}


class RazorpayPaymentGateway:
    provider = "razorpay"

    def __init__(
        self,
        *,
        key_id: str,
        key_secret: str,
        webhook_secret: str,
        api_base_url: str,
        callback_url: str,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._key_id = key_id
        self._key_secret = key_secret
        self._webhook_secret = webhook_secret
        self._api_base_url = api_base_url.rstrip("/")
        self._callback_url = callback_url
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    @property
    def is_configured(self) -> bool:
        return bool(self._key_id and self._key_secret)

    async def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                base_url=self._api_base_url,
                auth=(self._key_id, self._key_secret),
                timeout=self._timeout_seconds,
                transport=self._transport,
            ) as client:
                response = await client.request(method, path, json=payload)
        except httpx.HTTPError as exc:
            msg = f"Razorpay request failed: {type(exc).__name__}"
            raise PaymentGatewayError(msg) from exc

        if response.status_code >= 400:
            # Razorpay's error body carries a description, never credentials.
            try:
                description = response.json().get("error", {}).get("description", "")
            except ValueError:
                description = ""
            _logger.warning(
                "razorpay_request_rejected",
                path=path,
                status_code=response.status_code,
                description=description,
            )
            msg = f"Razorpay returned HTTP {response.status_code}: {description}"
            raise PaymentGatewayError(msg)
        body: dict[str, Any] = response.json()
        return body

    async def verify_credentials(self) -> None:
        await self._request("GET", "/payment_links?count=1")

    async def create_payment_link(self, request: PaymentLinkRequest) -> PaymentLink:
        payload: dict[str, Any] = {
            "amount": to_paise(request.amount),
            "currency": request.currency,
            "accept_partial": False,
            "reference_id": request.reference_id,
            "description": request.description,
            "notes": request.notes,
            # Our own SMS / WhatsApp channels deliver the link; Razorpay's
            # notifications would message the customer a second time.
            "notify": {"sms": False, "email": False},
            "reminder_enable": False,
        }
        customer = {
            key: value
            for key, value in (
                ("name", request.customer_name),
                ("contact", request.customer_phone),
                ("email", request.customer_email),
            )
            if value
        }
        if customer:
            payload["customer"] = customer
        if request.expires_at is not None:
            payload["expire_by"] = int(request.expires_at.timestamp())
        if self._callback_url:
            payload["callback_url"] = self._callback_url
            payload["callback_method"] = "get"

        body = await self._request("POST", "/payment_links", payload)
        return PaymentLink(link_id=str(body["id"]), short_url=str(body["short_url"]))

    async def fetch_payment_link(self, link_id: str) -> PaymentLinkStatus:
        body = await self._request("GET", f"/payment_links/{link_id}")
        status = _LINK_STATUS_MAP.get(str(body.get("status")), "created")
        payment_id: str | None = None
        paid_at: datetime | None = None
        if status == "paid":
            captured = [p for p in body.get("payments") or [] if p.get("status") == "captured"]
            if captured:
                payment_id = str(captured[-1].get("payment_id") or "") or None
                paid_at = _timestamp(captured[-1].get("created_at"))
        return PaymentLinkStatus(
            link_id=link_id,
            status=status,
            provider_payment_id=payment_id,
            payment_method=None,
            paid_at=paid_at,
            notes=_notes(body),
        )

    def verify_signature(self, body: bytes, signature: str | None) -> None:
        if not self._webhook_secret or not signature:
            raise InvalidWebhookSignatureError
        expected = hmac.new(self._webhook_secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise InvalidWebhookSignatureError

    def parse_webhook(self, body: bytes, signature: str | None) -> PaymentLinkStatus | None:
        self.verify_signature(body, signature)
        try:
            event = json.loads(body)
        except ValueError:
            return None
        if not isinstance(event, dict) or event.get("event") not in _HANDLED_EVENTS:
            return None

        payload = event.get("payload") or {}
        link = (payload.get("payment_link") or {}).get("entity") or {}
        payment = (payload.get("payment") or {}).get("entity") or {}
        link_id = link.get("id")
        if not link_id:
            return None

        status = _LINK_STATUS_MAP.get(str(link.get("status")), "created")
        if event["event"] == "payment_link.paid":
            status = "paid"
        return PaymentLinkStatus(
            link_id=str(link_id),
            status=status,
            provider_payment_id=str(payment["id"]) if payment.get("id") else None,
            payment_method=str(payment["method"]) if payment.get("method") else None,
            paid_at=_timestamp(payment.get("created_at")) if status == "paid" else None,
            notes=_notes(link),
        )
