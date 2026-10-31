"""Keyless `PaymentGateway` for demos and tests (ADR-066).

Creates a link that points at a plain explanation page and never moves
money. A link becomes paid only when staff use "simulate paid"
(`POST /online-payments/{id}/simulate-paid`), which feeds a `paid` status
through the same code path a real Razorpay webhook uses. Refused in
production unless `LPG_PAYMENTS_ALLOW_MOCK=true`.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from lpg.application.accounting.payment_gateway import PaymentLink, PaymentLinkStatus

if TYPE_CHECKING:
    from lpg.application.accounting.payment_gateway import PaymentLinkRequest


class MockPaymentGateway:
    provider = "mock"
    is_configured = True

    def __init__(self, *, public_base_url: str) -> None:
        self._public_base_url = public_base_url.rstrip("/")

    async def verify_credentials(self) -> None:
        return None

    async def create_payment_link(self, request: PaymentLinkRequest) -> PaymentLink:  # noqa: ARG002
        link_id = f"mock_{uuid.uuid4().hex[:16]}"
        return PaymentLink(
            link_id=link_id,
            short_url=f"{self._public_base_url}/api/v1/payments/mock/{link_id}",
        )

    async def fetch_payment_link(self, link_id: str) -> PaymentLinkStatus:
        return PaymentLinkStatus(link_id=link_id, status="created")

    def parse_webhook(self, body: bytes, signature: str | None) -> PaymentLinkStatus | None:  # noqa: ARG002
        return None
