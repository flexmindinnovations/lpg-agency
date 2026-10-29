"""The agency's payment profile: bank account, UPI ID, invoice footer (ADR-066).

Stored as one historised tenant-configuration value (`payment_profile`), so
an invoice reprinted next year can still be traced to what was current when
it was changed. Validation lives here so the dashboard, the apps and the
generic configuration endpoint cannot disagree about what a valid IFSC or
UPI ID looks like.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from urllib.parse import quote, urlencode

from lpg.application.common.errors import ValidationError
from lpg.application.tenant.tenant_configuration import (
    GetEffectiveTenantConfigurationQuery,
    GetEffectiveTenantConfigurationUseCase,
    SetTenantConfigurationCommand,
    SetTenantConfigurationUseCase,
)

if TYPE_CHECKING:
    import uuid

    from lpg.application.common.ports import UnitOfWork
    from lpg.application.tenant.ports import TenantConfigurationRepository

PAYMENT_PROFILE_KEY = "payment_profile"

_IFSC = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
_ACCOUNT_NUMBER = re.compile(r"^\d{9,18}$")
#: `name@handle` — the handle is the PSP (`okhdfcbank`, `ybl`, ...).
_VPA = re.compile(r"^[a-zA-Z0-9._-]{2,256}@[a-zA-Z][a-zA-Z0-9]{1,63}$")

_CENT = Decimal("0.01")


def is_valid_ifsc(ifsc: str) -> bool:
    return bool(_IFSC.match(ifsc))


def is_valid_vpa(upi_id: str) -> bool:
    return bool(_VPA.match(upi_id))


@dataclass(frozen=True, slots=True)
class PaymentProfile:
    account_holder: str = ""
    bank_name: str = ""
    account_number: str = ""
    ifsc: str = ""
    branch: str = ""
    upi_id: str = ""
    #: Name shown to the payer in their UPI app. Defaults to the account holder.
    upi_payee_name: str = ""
    invoice_footer_note: str = ""

    @property
    def has_bank_details(self) -> bool:
        return bool(self.account_number and self.ifsc)

    @property
    def has_upi(self) -> bool:
        return bool(self.upi_id)

    @property
    def payee_name(self) -> str:
        return self.upi_payee_name or self.account_holder

    @classmethod
    def from_config(cls, value: Any) -> PaymentProfile:
        if not isinstance(value, dict):
            return cls()
        known = {f: str(value.get(f) or "") for f in cls.__dataclass_fields__}
        return cls(**known)

    def to_config(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def validated(cls, **fields: str | None) -> PaymentProfile:
        """Trim, normalise and validate; a blank group is allowed (the agency
        may have UPI only, or a bank account only), a half-filled one is not.
        """
        clean = {k: (v or "").strip() for k, v in fields.items()}
        clean["ifsc"] = clean.get("ifsc", "").upper()
        clean["account_number"] = re.sub(r"\s+", "", clean.get("account_number", ""))
        clean["upi_id"] = clean.get("upi_id", "").lower()
        profile = cls(**clean)

        bank_parts = (profile.account_holder, profile.account_number, profile.ifsc)
        if any(bank_parts) and not all(bank_parts):
            msg = "Enter the account holder, account number and IFSC together, or leave them blank."
            raise ValidationError(msg, field="account_number")
        if profile.account_number and not _ACCOUNT_NUMBER.match(profile.account_number):
            msg = "Account number must be 9 to 18 digits."
            raise ValidationError(msg, field="account_number")
        if profile.account_number and len(set(profile.account_number)) == 1:
            msg = "That account number is not valid. Check it against your passbook."
            raise ValidationError(msg, field="account_number")
        if profile.ifsc and not _IFSC.match(profile.ifsc):
            msg = "IFSC must be 11 characters, like HDFC0001234."
            raise ValidationError(msg, field="ifsc")
        if profile.upi_id and not _VPA.match(profile.upi_id):
            msg = "UPI ID must look like name@bank."
            raise ValidationError(msg, field="upi_id")
        if profile.upi_id and not profile.payee_name:
            msg = "Add the payee name that customers should see when they pay by UPI."
            raise ValidationError(msg, field="upi_payee_name")
        return profile


def build_upi_uri(
    profile: PaymentProfile, *, amount: Decimal | None, note: str, reference: str | None = None
) -> str:
    """NPCI UPI deep link. Any UPI app opens it with payee and amount filled;
    `am` is omitted when no amount is given so the payer types it.
    """
    params: dict[str, str] = {
        "pa": profile.upi_id,
        "pn": profile.payee_name,
        "cu": "INR",
        "tn": note[:80],
    }
    if amount is not None:
        params["am"] = str(amount.quantize(_CENT))
    if reference:
        params["tr"] = reference[:35]
    return "upi://pay?" + urlencode(params, quote_via=quote)


class GetPaymentProfileUseCase:
    def __init__(self, repository: TenantConfigurationRepository) -> None:
        self._get = GetEffectiveTenantConfigurationUseCase(repository)

    async def execute(self, tenant_id: uuid.UUID, *, at: datetime | None = None) -> PaymentProfile:
        config = await self._get.execute(
            GetEffectiveTenantConfigurationQuery(
                tenant_id, PAYMENT_PROFILE_KEY, at or datetime.now(UTC)
            )
        )
        return PaymentProfile.from_config(config.config_value if config else None)


class SetPaymentProfileUseCase:
    def __init__(self, repository: TenantConfigurationRepository, unit_of_work: UnitOfWork) -> None:
        self._set = SetTenantConfigurationUseCase(repository, unit_of_work)

    async def execute(self, tenant_id: uuid.UUID, profile: PaymentProfile) -> PaymentProfile:
        await self._set.execute(
            SetTenantConfigurationCommand(tenant_id, PAYMENT_PROFILE_KEY, profile.to_config())
        )
        return profile
