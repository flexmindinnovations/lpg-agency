"""The default `PaymentLinkPort`: no online payment provider is configured.

The Razorpay integration replaces this with a real adapter; until then the
assistant tells customers to pay by cash or UPI on delivery.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lpg.application.whatsapp.ports import PaymentLink, PaymentLinkRequest


class UnconfiguredPaymentLinks:
    async def create_payment_link(self, request: PaymentLinkRequest) -> PaymentLink | None:  # noqa: ARG002
        return None
