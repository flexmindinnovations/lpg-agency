"""`SetLicenseFeatureOverrideUseCase` (`super_admin`, live-checked, mirrors
`SetTenantFeatureFlagOverrideUseCase`) and `ResolveLicenseEntitlementUseCase`
— the composable read API a future consumer (e.g. sidebar module gating)
would use to check "does this tenant's license grant feature X." Not
consumed anywhere in this codebase yet.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command
from lpg.application.common.errors import NotFoundError
from lpg.domain.license.license import LicenseEntitlementService, LicenseFeatureOverride

if TYPE_CHECKING:
    from lpg.application.common.ports import UnitOfWork
    from lpg.application.license.ports import (
        LicenseFeatureOverrideRepository,
        LicenseRepository,
    )


@dataclass(frozen=True, slots=True)
class SetLicenseFeatureOverrideCommand(Command):
    tenant_id: uuid.UUID
    feature_key: str
    granted: bool


class SetLicenseFeatureOverrideUseCase:
    """Creates the override on first use, updates it on every call after —
    a license only ever has one override per feature key, mirroring
    `SetTenantFeatureFlagOverrideUseCase`'s exact create-or-update shape."""

    def __init__(
        self,
        override_repository: LicenseFeatureOverrideRepository,
        license_repository: LicenseRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._override_repository = override_repository
        self._license_repository = license_repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: SetLicenseFeatureOverrideCommand) -> None:
        license_ = await self._license_repository.get_by_tenant_id(command.tenant_id)
        if license_ is None:
            msg = f"No license exists for tenant '{command.tenant_id}'."
            raise NotFoundError(msg, tenant_id=str(command.tenant_id))

        existing = await self._override_repository.get_for_license_and_feature(
            license_.id, command.feature_key
        )
        if existing is not None:
            existing.set_granted(granted=command.granted)
            await self._override_repository.save(existing)
        else:
            override = LicenseFeatureOverride(
                uuid.uuid4(), license_.id, command.feature_key, granted=command.granted
            )
            await self._override_repository.add(override)

        await self._unit_of_work.commit()


@dataclass(frozen=True, slots=True)
class ResolveLicenseEntitlementQuery:
    tenant_id: uuid.UUID
    feature_key: str


class ResolveLicenseEntitlementUseCase:
    def __init__(
        self,
        license_repository: LicenseRepository,
        override_repository: LicenseFeatureOverrideRepository,
    ) -> None:
        self._license_repository = license_repository
        self._override_repository = override_repository

    async def execute(self, query: ResolveLicenseEntitlementQuery) -> bool:
        license_ = await self._license_repository.get_by_tenant_id(query.tenant_id)
        if license_ is None:
            return False

        overrides = await self._override_repository.list_for_license(license_.id)
        return LicenseEntitlementService.is_feature_granted(
            license_, overrides, query.feature_key
        )
