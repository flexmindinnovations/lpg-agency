"""Payment gateway port (ADR-053).

Everything above infrastructure talks to a gateway only through
`PaymentGateway`; `infrastructure/payments/factory.py` picks the adapter
(Razorpay today). The port is shaped around *payment links* — a hosted
checkout page reachable by URL — because one mechanism then serves every
channel: the Customer App opens it in a browser, staff can share it, and
the WhatsApp assistant can send it in a message.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime
    from decimal import Decimal


class PaymentGatewayError(Exception):
    """The gateway rejected a request or could not be reached."""


class InvalidWebhookSignatureError(Exception):
    """A webhook body's signature did not verify — the request must be
    rejected without reading anything else from it.
    """


@dataclass(frozen=True, slots=True)
class PaymentLinkRequest:
    amount: Decimal
    currency: str
    #: Our `OnlinePayment.id` — echoed back by the gateway so a webhook can
    #: always be matched to the record that created it.
    reference_id: str
    description: str
    notes: dict[str, str]
    customer_name: str | None = None
    customer_phone: str | None = None
    customer_email: str | None = None
    expires_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class PaymentLink:
    link_id: str
    short_url: str


@dataclass(frozen=True, slots=True)
class PaymentLinkStatus:
    """A gateway's view of one link, normalised to our vocabulary.

    `status` is one of `created`, `paid`, `expired`, `cancelled`.
    """

    link_id: str
    status: str
    provider_payment_id: str | None = None
    payment_method: str | None = None
    paid_at: datetime | None = None
    notes: dict[str, str] = field(default_factory=dict)


class PaymentGateway(Protocol):
    @property
    def provider(self) -> str:
        """Stable provider code persisted on every `OnlinePayment`."""

    @property
    def is_configured(self) -> bool:
        """`False` when credentials are missing — callers answer 503
        instead of sending an unauthenticated request.
        """

    async def create_payment_link(self, request: PaymentLinkRequest) -> PaymentLink: ...

    async def fetch_payment_link(self, link_id: str) -> PaymentLinkStatus: ...

    def parse_webhook(self, body: bytes, signature: str | None) -> PaymentLinkStatus | None:
        """Verify `signature` over the raw `body`, then normalise the event.

        Raises `InvalidWebhookSignatureError` if verification fails. Returns
        `None` for a verified event this integration does not act on.
        """
        ...
