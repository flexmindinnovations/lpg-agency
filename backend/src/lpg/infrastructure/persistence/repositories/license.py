"""`SqlAlchemyLicenseRepository`/`SqlAlchemyLicenseFeatureOverrideRepository`/
`SqlAlchemyLinkedDeviceRepository` — implement `application/license/ports.py`.

Same `SqlAlchemyUnitOfWork`-backed shape as `SqlAlchemyFeatureFlagRepository`,
used by every authenticated `/admin/license/*` use case — the normal
RLS-scoped path (migration `92e48f9bf322`), reading/writing through the
tenant-scoped session `get_unit_of_work` already establishes.

Deliberately **not** used by `LoginUseCase`/`RefreshTokenUseCase` — those run
before any tenant context exists and therefore before any `UnitOfWork` (or
the `app.current_tenant_id` session variable RLS depends on) can be
constructed (`application/identity/login.py`'s own module docstring). That
pre-auth read path goes through `platform.license_find_by_tenant_id`, a
narrow `SECURITY DEFINER` SQL function, in
`infrastructure/license/license_status_cache.py`'s `RedisLicenseStatusChecker`
— the same resolution `SqlAlchemyIdentityUserRepository` already uses for
`identity.identity_user`.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func, select, text

from lpg.domain.license.license import License, LicenseFeatureOverride
from lpg.domain.license.linked_device import LinkedDevice
from lpg.infrastructure.persistence.models.platform import (
    LicenseFeatureOverrideModel,
    LicenseModel,
    LinkedDeviceModel,
)

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


def license_from_row(row: LicenseModel) -> License:
    return License(
        row.id,
        row.tenant_id,
        row.key_hash,
        row.key_prefix,
        row.plan_tier,
        timedelta(seconds=row.validity_period_seconds),
        row.issued_at,
        device_caps=dict(row.device_caps or {}),
        activated_at=row.activated_at,
        revoked_at=row.revoked_at,
        version=row.version,
    )


class SqlAlchemyLicenseRepository:
    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    async def get(self, license_id: uuid.UUID) -> License | None:
        row = await self._uow.session.get(LicenseModel, license_id)
        if row is None:
            return None

        license_ = license_from_row(row)
        self._uow.register_aggregate(license_)
        return license_

    async def get_by_tenant_id(self, tenant_id: uuid.UUID) -> License | None:
        """The tenant's *current* license — or, if none is active, its most
        recently revoked one, never an arbitrary older row.

        More than one row per tenant is possible since `f5746de5730e` made
        `uq_license_tenant_id` a partial index (`WHERE revoked_at IS NULL`):
        a tenant can hold any number of past revoked licenses, but at most
        one non-revoked one — so `ORDER BY issued_at DESC LIMIT 1` always
        resolves to that one non-revoked row when it exists, and correctly
        falls back to the last revoked row (not `None`, which would
        misreport a revoked tenant as merely `PENDING_ACTIVATION`) when it
        doesn't.
        """
        result = await self._uow.session.execute(
            select(LicenseModel)
            .where(LicenseModel.tenant_id == tenant_id)
            .order_by(LicenseModel.issued_at.desc())
            .limit(1)
        )
        row = result.scalars().first()
        if row is None:
            return None

        license_ = license_from_row(row)
        self._uow.register_aggregate(license_)
        return license_

    async def list_all(self) -> Sequence[License]:
        """Every tenant's license, platform-wide. Was previously a plain
        `SELECT` — RLS-scoped like every other query in this repository —
        which meant this always silently returned at most the *caller's*
        own license, never "every tenant's", despite the endpoint's own
        name. Reads through `platform.license_list_all()`, a `SECURITY
        DEFINER` function that bypasses RLS regardless of whatever
        `app.current_tenant_id` this session has set (migration
        `fdd3afde337c`) — the actual fix, not just a rename.
        """
        result = await self._uow.session.execute(
            text("SELECT * FROM platform.license_list_all()")
        )
        return [
            License(
                row.id,
                row.tenant_id,
                row.key_hash,
                row.key_prefix,
                row.plan_tier,
                timedelta(seconds=row.validity_period_seconds),
                row.issued_at,
                device_caps=dict(row.device_caps or {}),
                activated_at=row.activated_at,
                revoked_at=row.revoked_at,
                version=row.version,
            )
            for row in result
        ]

    async def add(self, license: License) -> None:
        self._uow.session.add(
            LicenseModel(
                id=license.id,
                tenant_id=license.tenant_id,
                key_hash=license.key_hash,
                key_prefix=license.key_prefix,
                plan_tier=license.plan_tier,
                validity_period_seconds=int(license.validity_period.total_seconds()),
                device_caps=license.device_caps,
                issued_at=license.issued_at,
                activated_at=license.activated_at,
                revoked_at=license.revoked_at,
            )
        )
        self._uow.register_aggregate(license)

    async def save(self, license: License) -> None:
        row = await self._uow.session.get(LicenseModel, license.id)
        if row is None:
            msg = f"Cannot save license {license.id} — no matching row was loaded."
            raise LookupError(msg)

        row.plan_tier = license.plan_tier
        row.device_caps = license.device_caps
        row.activated_at = license.activated_at
        row.revoked_at = license.revoked_at


class SqlAlchemyLicenseFeatureOverrideRepository:
    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    async def get_for_license_and_feature(
        self, license_id: uuid.UUID, feature_key: str
    ) -> LicenseFeatureOverride | None:
        result = await self._uow.session.execute(
            select(LicenseFeatureOverrideModel).where(
                LicenseFeatureOverrideModel.license_id == license_id,
                LicenseFeatureOverrideModel.feature_key == feature_key,
            )
        )
        row = result.scalars().first()
        if row is None:
            return None

        override = self._to_domain(row)
        self._uow.register_aggregate(override)
        return override

    async def list_for_license(self, license_id: uuid.UUID) -> Sequence[LicenseFeatureOverride]:
        result = await self._uow.session.execute(
            select(LicenseFeatureOverrideModel).where(
                LicenseFeatureOverrideModel.license_id == license_id
            )
        )
        return [self._to_domain(row) for row in result.scalars()]

    async def add(self, override: LicenseFeatureOverride) -> None:
        self._uow.session.add(
            LicenseFeatureOverrideModel(
                id=override.id,
                license_id=override.license_id,
                feature_key=override.feature_key,
                granted=override.granted,
            )
        )
        self._uow.register_aggregate(override)

    async def save(self, override: LicenseFeatureOverride) -> None:
        row = await self._uow.session.get(LicenseFeatureOverrideModel, override.id)
        if row is None:
            msg = f"Cannot save license feature override {override.id} — no matching row."
            raise LookupError(msg)

        row.granted = override.granted

    @staticmethod
    def _to_domain(row: LicenseFeatureOverrideModel) -> LicenseFeatureOverride:
        return LicenseFeatureOverride(
            row.id, row.license_id, row.feature_key, granted=row.granted, version=row.version
        )


class SqlAlchemyLinkedDeviceRepository:
    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    async def get(self, device_id: uuid.UUID) -> LinkedDevice | None:
        row = await self._uow.session.get(LinkedDeviceModel, device_id)
        if row is None:
            return None

        device = self._to_domain(row)
        self._uow.register_aggregate(device)
        return device

    async def get_by_identifier(
        self, tenant_id: uuid.UUID, app_type: str, device_identifier: str
    ) -> LinkedDevice | None:
        result = await self._uow.session.execute(
            select(LinkedDeviceModel).where(
                LinkedDeviceModel.tenant_id == tenant_id,
                LinkedDeviceModel.app_type == app_type,
                LinkedDeviceModel.device_identifier == device_identifier,
            )
        )
        row = result.scalars().first()
        if row is None:
            return None

        device = self._to_domain(row)
        self._uow.register_aggregate(device)
        return device

    async def list_for_tenant(
        self, tenant_id: uuid.UUID, app_type: str | None = None
    ) -> Sequence[LinkedDevice]:
        stmt = select(LinkedDeviceModel).where(LinkedDeviceModel.tenant_id == tenant_id)
        if app_type is not None:
            stmt = stmt.where(LinkedDeviceModel.app_type == app_type)
        result = await self._uow.session.execute(stmt.order_by(LinkedDeviceModel.registered_at))
        return [self._to_domain(row) for row in result.scalars()]

    async def count_active_for_app_type(self, tenant_id: uuid.UUID, app_type: str) -> int:
        result = await self._uow.session.execute(
            select(func.count()).where(
                LinkedDeviceModel.tenant_id == tenant_id,
                LinkedDeviceModel.app_type == app_type,
                LinkedDeviceModel.revoked_at.is_(None),
            )
        )
        return result.scalar_one()

    async def add(self, device: LinkedDevice) -> None:
        self._uow.session.add(
            LinkedDeviceModel(
                id=device.id,
                tenant_id=device.tenant_id,
                license_id=device.license_id,
                app_type=device.app_type,
                device_identifier=device.device_identifier,
                display_name=device.display_name,
                registered_at=device.registered_at,
                last_seen_at=device.last_seen_at,
                revoked_at=device.revoked_at,
            )
        )
        self._uow.register_aggregate(device)

    async def save(self, device: LinkedDevice) -> None:
        row = await self._uow.session.get(LinkedDeviceModel, device.id)
        if row is None:
            msg = f"Cannot save device {device.id} — no matching row was loaded."
            raise LookupError(msg)

        row.display_name = device.display_name
        row.last_seen_at = device.last_seen_at
        row.revoked_at = device.revoked_at

    @staticmethod
    def _to_domain(row: LinkedDeviceModel) -> LinkedDevice:
        return LinkedDevice(
            row.id,
            row.tenant_id,
            row.license_id,
            row.app_type,
            row.device_identifier,
            row.display_name,
            row.registered_at,
            last_seen_at=row.last_seen_at,
            revoked_at=row.revoked_at,
            version=row.version,
        )
