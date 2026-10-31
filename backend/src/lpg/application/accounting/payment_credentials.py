"""An agency's own Razorpay credentials (ADR-067).

Every agency has its own Razorpay account, so the key pair and webhook
secret live per tenant, not in platform environment variables. This module
holds the rules; persistence and encryption are behind
`PaymentCredentialRepository`.

Secrets are write-only: nothing here returns a stored secret to an API
caller. `PaymentGatewaySettings` carries a masked key id and "is a secret
set" flags only.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal, Protocol

from lpg.application.common.errors import NotFoundError, ValidationError

if TYPE_CHECKING:
    import uuid

    from lpg.application.common.ports import UnitOfWork

_KEY_ID = re.compile(r"^rzp_(test|live)_[A-Za-z0-9]{6,40}$")

Mode = Literal["test", "live"]
#: Where payments will go when the agency asks for a payment link.
Source = Literal["agency", "platform", "demo", "none"]


def mode_of(key_id: str) -> Mode | None:
    """`test` or `live`, from Razorpay's own key prefix."""
    if key_id.startswith("rzp_test_"):
        return "test"
    if key_id.startswith("rzp_live_"):
        return "live"
    return None


def mask_key_id(key_id: str) -> str:
    """`rzp_live_••••••1234`: the mode prefix and last four, nothing else."""
    mode = mode_of(key_id)
    if mode is None or len(key_id) < 4:
        return "••••"
    return f"rzp_{mode}_••••••{key_id[-4:]}"


@dataclass(frozen=True, slots=True)
class StoredPaymentCredentials:
    """Decrypted, in memory only. Never serialise this into a response."""

    tenant_id: uuid.UUID
    key_id: str
    key_secret: str
    webhook_secret: str | None
    webhook_token: str
    updated_at: datetime
    updated_by: uuid.UUID | None = None

    @property
    def mode(self) -> Mode | None:
        return mode_of(self.key_id)


@dataclass(frozen=True, slots=True)
class PaymentGatewaySettings:
    configured: bool
    key_id_masked: str = ""
    mode: Mode | None = None
    has_key_secret: bool = False
    has_webhook_secret: bool = False
    webhook_token: str = ""
    updated_at: datetime | None = None
    source: Source = "none"


class PaymentCredentialRepository(Protocol):
    """One row per tenant; encrypts on the way in and decrypts on the way out."""

    async def get(self) -> StoredPaymentCredentials | None: ...

    async def save(self, credentials: StoredPaymentCredentials) -> None:
        """Insert or replace the tenant's credentials."""

    async def delete(self) -> bool:
        """`True` if a row existed."""


class WebhookTenantResolver(Protocol):
    """Opaque webhook URL token -> tenant (the webhook has no JWT)."""

    async def resolve(self, token: str) -> uuid.UUID | None: ...


def new_webhook_token() -> str:
    return secrets.token_urlsafe(24)


def to_settings(
    stored: StoredPaymentCredentials | None, *, fallback: Source
) -> PaymentGatewaySettings:
    if stored is None:
        return PaymentGatewaySettings(configured=False, source=fallback)
    return PaymentGatewaySettings(
        configured=True,
        key_id_masked=mask_key_id(stored.key_id),
        mode=stored.mode,
        has_key_secret=bool(stored.key_secret),
        has_webhook_secret=bool(stored.webhook_secret),
        webhook_token=stored.webhook_token,
        updated_at=stored.updated_at,
        source="agency",
    )


class GetPaymentGatewaySettingsUseCase:
    def __init__(self, repository: PaymentCredentialRepository) -> None:
        self._repository = repository

    async def execute(self, *, fallback: Source) -> PaymentGatewaySettings:
        return to_settings(await self._repository.get(), fallback=fallback)


@dataclass(frozen=True, slots=True)
class SetPaymentCredentialsCommand:
    tenant_id: uuid.UUID
    updated_by: uuid.UUID | None
    #: Blank keeps the saved key id.
    key_id: str
    #: Blank keeps the stored secret (when the key id is unchanged).
    key_secret: str = ""
    #: Blank keeps the stored webhook secret.
    webhook_secret: str = ""


class SetPaymentCredentialsUseCase:
    def __init__(
        self,
        repository: PaymentCredentialRepository,
        unit_of_work: UnitOfWork,
        *,
        fallback: Source,
    ) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work
        self._fallback = fallback

    async def execute(self, command: SetPaymentCredentialsCommand) -> PaymentGatewaySettings:
        existing = await self._repository.get()
        # Blank keeps the saved key id (to change only a secret).
        key_id = command.key_id.strip() or (existing.key_id if existing else "")
        if not _KEY_ID.match(key_id):
            msg = (
                "A Razorpay key id looks like rzp_live_… or rzp_test_… "
                "(Razorpay dashboard > Account & Settings > API Keys)."
            )
            raise ValidationError(msg)
        key_secret = command.key_secret.strip()
        if not key_secret:
            if existing is None or existing.key_id != key_id:
                msg = "Enter the key secret that goes with this key id."
                raise ValidationError(msg)
            key_secret = existing.key_secret
        webhook_secret = command.webhook_secret.strip() or (
            existing.webhook_secret if existing else None
        )

        stored = StoredPaymentCredentials(
            tenant_id=command.tenant_id,
            key_id=key_id,
            key_secret=key_secret,
            webhook_secret=webhook_secret,
            webhook_token=existing.webhook_token if existing else new_webhook_token(),
            updated_at=datetime.now(UTC),
            updated_by=command.updated_by,
        )
        await self._repository.save(stored)
        await self._unit_of_work.commit()
        return to_settings(stored, fallback=self._fallback)


class RemovePaymentCredentialsUseCase:
    def __init__(self, repository: PaymentCredentialRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self) -> None:
        if not await self._repository.delete():
            msg = "This agency has no Razorpay credentials saved."
            raise NotFoundError(msg)
        await self._unit_of_work.commit()


class RotateWebhookTokenUseCase:
    """New opaque webhook URL, e.g. after it leaked. The old URL stops working
    at once; the agency must register the new one in Razorpay.
    """

    def __init__(
        self,
        repository: PaymentCredentialRepository,
        unit_of_work: UnitOfWork,
        *,
        fallback: Source,
    ) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work
        self._fallback = fallback

    async def execute(self, *, updated_by: uuid.UUID | None) -> PaymentGatewaySettings:
        existing = await self._repository.get()
        if existing is None:
            msg = "Save your Razorpay key first."
            raise NotFoundError(msg)
        rotated = StoredPaymentCredentials(
            tenant_id=existing.tenant_id,
            key_id=existing.key_id,
            key_secret=existing.key_secret,
            webhook_secret=existing.webhook_secret,
            webhook_token=new_webhook_token(),
            updated_at=datetime.now(UTC),
            updated_by=updated_by,
        )
        await self._repository.save(rotated)
        await self._unit_of_work.commit()
        return to_settings(rotated, fallback=self._fallback)
