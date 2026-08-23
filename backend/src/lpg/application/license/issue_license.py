"""Platform-side license management — `super_admin` only, all live-checked
(`require_live_permission("license:manage_platform")`), the same
sensitivity tier `feature_flags:manage_platform` uses.
"""

from __future__ import annotations

import base64
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command
from lpg.application.common.errors import LicenseAlreadyIssuedError, NotFoundError
from lpg.domain.license.license import License

if TYPE_CHECKING:
    from lpg.application.common.ports import UnitOfWork
    from lpg.application.identity.ports import TokenHasher
    from lpg.application.license.ports import LicenseRepository, LicenseStatusChecker


def _generate_license_key() -> str:
    """`LPG-XXXX-XXXX-XXXX-XXXX` — 10 random bytes (80 bits, well beyond
    brute-force feasible for a key that's also rate-limited at the
    activation endpoint) as RFC 4648 base32 (32-symbol alphabet, no padding
    needed at this exact byte count), grouped for readability."""
    raw = secrets.token_bytes(10)
    encoded = base64.b32encode(raw).decode("ascii")  # 16 chars, no padding
    groups = [encoded[i : i + 4] for i in range(0, len(encoded), 4)]
    return "LPG-" + "-".join(groups)


@dataclass(frozen=True, slots=True)
class IssueLicenseCommand(Command):
    tenant_id: uuid.UUID
    plan_tier: str
    validity_period: timedelta = timedelta(days=365)
    device_caps: dict[str, int | None] | None = None


class IssueLicenseUseCase:
    """Returns `(License, plaintext_key)` — the plaintext exists only here
    and in the one response DTO that echoes it back once. It is never
    reconstructible after this call returns."""

    def __init__(
        self,
        repository: LicenseRepository,
        token_hasher: TokenHasher,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._token_hasher = token_hasher
        self._unit_of_work = unit_of_work

    async def execute(self, command: IssueLicenseCommand) -> tuple[License, str]:
        existing = await self._repository.get_by_tenant_id(command.tenant_id)
        if existing is not None and existing.revoked_at is None:
            msg = f"Tenant '{command.tenant_id}' already has an active license."
            raise LicenseAlreadyIssuedError(msg, tenant_id=str(command.tenant_id))

        plaintext_key = _generate_license_key()
        key_prefix = "-".join(plaintext_key.split("-")[:2])  # e.g. "LPG-7K2M"

        license_ = License(
            uuid.uuid4(),
            command.tenant_id,
            self._token_hasher.hash(plaintext_key),
            key_prefix,
            command.plan_tier,
            command.validity_period,
            datetime.now(UTC),
            device_caps=command.device_caps,
        )
        await self._repository.add(license_)
        await self._unit_of_work.commit()
        return license_, plaintext_key


@dataclass(frozen=True, slots=True)
class RevokeLicenseCommand(Command):
    tenant_id: uuid.UUID


class RevokeLicenseUseCase:
    def __init__(
        self,
        repository: LicenseRepository,
        status_checker: LicenseStatusChecker,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._status_checker = status_checker
        self._unit_of_work = unit_of_work

    async def execute(self, command: RevokeLicenseCommand) -> None:
        license_ = await self._repository.get_by_tenant_id(command.tenant_id)
        if license_ is None:
            msg = f"No license exists for tenant '{command.tenant_id}'."
            raise NotFoundError(msg, tenant_id=str(command.tenant_id))

        license_.revoke(at=datetime.now(UTC))

        await self._repository.save(license_)
        await self._unit_of_work.commit()
        await self._status_checker.invalidate(command.tenant_id)


@dataclass(frozen=True, slots=True)
class SetLicensePlanTierCommand(Command):
    tenant_id: uuid.UUID
    plan_tier: str


class SetLicensePlanTierUseCase:
    def __init__(self, repository: LicenseRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: SetLicensePlanTierCommand) -> None:
        license_ = await self._repository.get_by_tenant_id(command.tenant_id)
        if license_ is None or license_.revoked_at is not None:
            # `get_by_tenant_id` falls back to the most recently revoked row
            # when no active one exists (see its own docstring) — a
            # revoked license is a historical record, not something a
            # plan-tier change should silently land on.
            msg = f"No active license exists for tenant '{command.tenant_id}'."
            raise NotFoundError(msg, tenant_id=str(command.tenant_id))

        license_.set_plan_tier(command.plan_tier)

        await self._repository.save(license_)
        await self._unit_of_work.commit()


@dataclass(frozen=True, slots=True)
class SetLicenseDeviceCapCommand(Command):
    tenant_id: uuid.UUID
    app_type: str
    max_devices: int | None


class SetLicenseDeviceCapUseCase:
    def __init__(self, repository: LicenseRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: SetLicenseDeviceCapCommand) -> None:
        license_ = await self._repository.get_by_tenant_id(command.tenant_id)
        if license_ is None or license_.revoked_at is not None:
            # See `SetLicensePlanTierUseCase`'s identical guard.
            msg = f"No active license exists for tenant '{command.tenant_id}'."
            raise NotFoundError(msg, tenant_id=str(command.tenant_id))

        license_.set_device_cap(command.app_type, command.max_devices)

        await self._repository.save(license_)
        await self._unit_of_work.commit()


@dataclass(frozen=True, slots=True)
class ListLicensesQuery:
    pass


class ListLicensesUseCase:
    def __init__(self, repository: LicenseRepository) -> None:
        self._repository = repository

    async def execute(self, query: ListLicensesQuery) -> list[License]:
        del query
        return list(await self._repository.list_all())
