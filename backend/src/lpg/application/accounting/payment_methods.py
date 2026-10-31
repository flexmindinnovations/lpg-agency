"""Which ways of paying an agency offers, worked out from its own set-up.

Nothing here is a fixed list. The apps ask once and show only what the
agency has configured (ADR-067, ADR-066):

- cash — always: it needs no provider.
- UPI — when the payment profile holds a UPI ID (the QR is built from it).
- Online payment — when the agency's own Razorpay account is connected.
- Bank transfer — when the payment profile holds bank details.
- On credit — when a credit limit is configured, because otherwise nothing
  bounds what a customer may take on account.
- Cheque — recorded at the office only; it needs no provider.

Card is not offered: the platform has no card-machine set-up to configure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from lpg.application.accounting.payment_profile import GetPaymentProfileUseCase
from lpg.application.tenant.tenant_configuration import (
    GetEffectiveTenantConfigurationQuery,
    GetEffectiveTenantConfigurationUseCase,
)

if TYPE_CHECKING:
    import uuid

    from lpg.application.tenant.ports import TenantConfigurationRepository

#: Same key the booking policy reads (`order.booking_policies`).
CREDIT_LIMIT_CONFIG_KEY = "credit_limit_default"

_LABELS: dict[str, str] = {
    "cash": "Cash",
    "upi": "UPI",
    "online_gateway": "Online payment",
    "credit": "On credit",
    "cheque": "Cheque",
    "bank_transfer": "Bank transfer",
}


@dataclass(frozen=True, slots=True)
class PaymentMethodOption:
    code: str
    label: str


@dataclass(frozen=True, slots=True)
class OfferedPaymentMethods:
    #: What a customer may prefer when booking an order.
    booking: tuple[PaymentMethodOption, ...]
    #: What the driver may record at the door.
    delivery: tuple[PaymentMethodOption, ...]
    #: What the office may record against an invoice.
    office: tuple[PaymentMethodOption, ...]


def _options(codes: list[str]) -> tuple[PaymentMethodOption, ...]:
    return tuple(PaymentMethodOption(code, _LABELS[code]) for code in codes)


def offered_methods(
    *,
    has_upi: bool,
    has_bank_details: bool,
    online_available: bool,
    credit_enabled: bool,
) -> OfferedPaymentMethods:
    booking = ["cash"]
    if has_upi:
        booking.append("upi")
    if online_available:
        booking.append("online_gateway")

    delivery = list(booking)
    if credit_enabled:
        delivery.append("credit")

    office = ["cash"]
    if has_upi:
        office.append("upi")
    office.append("cheque")
    if has_bank_details:
        office.append("bank_transfer")

    return OfferedPaymentMethods(_options(booking), _options(delivery), _options(office))


class ListPaymentMethodsUseCase:
    def __init__(self, repository: TenantConfigurationRepository) -> None:
        self._profile = GetPaymentProfileUseCase(repository)
        self._config = GetEffectiveTenantConfigurationUseCase(repository)

    async def execute(
        self, tenant_id: uuid.UUID, *, online_available: bool
    ) -> OfferedPaymentMethods:
        profile = await self._profile.execute(tenant_id)
        credit = await self._config.execute(
            GetEffectiveTenantConfigurationQuery(
                tenant_id, CREDIT_LIMIT_CONFIG_KEY, datetime.now(UTC)
            )
        )
        return offered_methods(
            has_upi=profile.has_upi,
            has_bank_details=profile.has_bank_details,
            online_available=online_available,
            credit_enabled=credit is not None and credit.config_value not in (None, "", {}),
        )
