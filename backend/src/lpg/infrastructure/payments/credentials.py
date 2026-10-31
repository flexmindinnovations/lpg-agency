"""Resolves which Razorpay account a tenant's payments go through (ADR-067).

An agency that saved its own key uses it; an agency that did not falls back
to the platform default (`Settings.razorpay_*`, or the demo gateway), so
existing deployments keep working unchanged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lpg.infrastructure.payments.factory import get_payment_gateway
from lpg.infrastructure.payments.razorpay import RazorpayPaymentGateway

if TYPE_CHECKING:
    from collections.abc import Callable

    from lpg.application.accounting.payment_credentials import (
        PaymentCredentialRepository,
        Source,
        StoredPaymentCredentials,
    )
    from lpg.application.accounting.payment_gateway import PaymentGateway
    from lpg.config.settings import Settings


def gateway_from_credentials(
    settings: Settings, credentials: StoredPaymentCredentials
) -> PaymentGateway:
    return RazorpayPaymentGateway(
        key_id=credentials.key_id,
        key_secret=credentials.key_secret,
        webhook_secret=credentials.webhook_secret or "",
        api_base_url=settings.razorpay_api_base_url,
        callback_url=settings.payment_link_callback_url,
        timeout_seconds=settings.razorpay_timeout_seconds,
    )


async def resolve_payment_gateway(
    settings: Settings,
    repository: PaymentCredentialRepository,
    *,
    fallback: Callable[[Settings], PaymentGateway] = get_payment_gateway,
) -> PaymentGateway:
    credentials = await repository.get()
    if credentials is not None:
        return gateway_from_credentials(settings, credentials)
    return fallback(settings)


def platform_fallback(settings: Settings) -> Source:
    """What an agency without its own key gets, for the Settings page."""
    if settings.payments_provider == "mock":
        return "demo"
    return "platform" if settings.razorpay_key_id else "none"
