"""Picks the `PaymentGateway` adapter from `Settings.payments_provider`.

Same "provider configurable" shape as `infrastructure/ai/factory.py`: a
second gateway is one new adapter plus one branch here. An unknown value
fails loudly rather than silently falling back to Razorpay.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lpg.application.accounting.payment_gateway import PaymentGateway
    from lpg.config.settings import Settings


def _secret(value: object) -> str:
    from pydantic import SecretStr

    return value.get_secret_value() if isinstance(value, SecretStr) else ""


def get_payment_gateway(settings: Settings) -> PaymentGateway:
    if settings.payments_provider == "razorpay":
        from lpg.infrastructure.payments.razorpay import RazorpayPaymentGateway

        return RazorpayPaymentGateway(
            key_id=settings.razorpay_key_id,
            key_secret=_secret(settings.razorpay_key_secret),
            webhook_secret=_secret(settings.razorpay_webhook_secret),
            api_base_url=settings.razorpay_api_base_url,
            callback_url=settings.payment_link_callback_url,
            timeout_seconds=settings.razorpay_timeout_seconds,
        )
    if settings.payments_provider == "mock":
        from lpg.infrastructure.payments.mock import MockPaymentGateway

        return MockPaymentGateway(
            public_base_url=settings.payment_link_callback_url or settings.dashboard_url
        )
    msg = f"Unknown payments_provider '{settings.payments_provider}'. Use 'razorpay' or 'mock'."
    raise ValueError(msg)
