"""DA-09 and DA-28 against real PostgreSQL.

DA-09: the plaintext licence key is shown once. If it was lost before
activation, the licence could never be activated from the UI; a Super Admin
can now generate a new key (the old one stops working) and activate with it.

DA-28: activating a licence, or changing its plan tier, moves the agency off
"trial" and onto the licence's plan, so the Agencies list and the licence agree.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from lpg.application.common.errors import ConflictError, LicenseActivationFailedError
from lpg.application.common.tenant import RequestTenantContext
from lpg.application.license.activate_license import ActivateLicenseCommand, ActivateLicenseUseCase
from lpg.application.license.issue_license import (
    IssueLicenseCommand,
    IssueLicenseUseCase,
    ReplaceLicenseKeyCommand,
    ReplaceLicenseKeyUseCase,
    SetLicensePlanTierCommand,
    SetLicensePlanTierUseCase,
)
from lpg.domain.license.license import LicenseLifecycleState
from lpg.infrastructure.identity.token_hasher import Sha256TokenHasher
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.repositories.license import SqlAlchemyLicenseRepository
from lpg.infrastructure.persistence.repositories.tenant import SqlAlchemyTenantRepository
from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.application.common.ports import UnitOfWork
    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration

_HASHER = Sha256TokenHasher()


class _NoopStatusChecker:
    async def get_status(self, tenant_id: uuid.UUID) -> LicenseLifecycleState:
        del tenant_id
        return LicenseLifecycleState.ACTIVE

    async def invalidate(self, tenant_id: uuid.UUID) -> None:
        del tenant_id


@pytest.fixture
async def database(
    integration_settings: Settings, postgres_available: bool
) -> AsyncIterator[Database]:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable — start it with ./scripts/dev-up.sh")
    db = Database(integration_settings)
    db.connect()
    try:
        yield db
    finally:
        await db.disconnect()


async def _seed_trial_tenant(admin_engine: AsyncEngine) -> uuid.UUID:
    async with admin_engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'Licence Sync Co', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"licence-sync-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
        await conn.execute(
            text("DELETE FROM platform.license WHERE tenant_id = :tenant_id"),
            {"tenant_id": str(tenant_id)},
        )
    return uuid.UUID(str(tenant_id))


async def _in_uow[T](
    database: Database, tenant_id: uuid.UUID, work: Callable[[UnitOfWork], Awaitable[T]]
) -> T:
    context = RequestTenantContext(tenant_id=tenant_id)
    async for session in database.open_session(tenant_id=tenant_id):
        async with SqlAlchemyUnitOfWork(session, context) as uow:
            return await work(uow)
    raise AssertionError  # pragma: no cover


async def _tenant_row(admin_engine: AsyncEngine, tenant_id: uuid.UUID) -> tuple[str, str]:
    async with admin_engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT status, subscription_plan FROM tenant.tenant WHERE id = :id"),
                {"id": str(tenant_id)},
            )
        ).one()
    return row.status, row.subscription_plan


async def test_a_lost_key_can_be_replaced_and_the_licence_activated(
    database: Database, admin_engine: AsyncEngine
) -> None:
    tenant_id = await _seed_trial_tenant(admin_engine)

    _issued, lost_key = await _in_uow(
        database,
        tenant_id,
        lambda uow: IssueLicenseUseCase(
            SqlAlchemyLicenseRepository(uow),  # type: ignore[arg-type]
            _HASHER,
            uow,
        ).execute(IssueLicenseCommand(tenant_id=tenant_id, plan_tier="premium")),
    )
    _replaced, new_key = await _in_uow(
        database,
        tenant_id,
        lambda uow: ReplaceLicenseKeyUseCase(
            SqlAlchemyLicenseRepository(uow),  # type: ignore[arg-type]
            _HASHER,
            uow,
        ).execute(ReplaceLicenseKeyCommand(tenant_id=tenant_id)),
    )
    assert new_key != lost_key

    def _activate(key: str) -> Callable[[UnitOfWork], Awaitable[object]]:
        return lambda uow: ActivateLicenseUseCase(
            SqlAlchemyLicenseRepository(uow),  # type: ignore[arg-type]
            _HASHER,
            _NoopStatusChecker(),
            uow,
            SqlAlchemyTenantRepository(uow),  # type: ignore[arg-type]
        ).execute(ActivateLicenseCommand(tenant_id=tenant_id, presented_key=key))

    with pytest.raises(LicenseActivationFailedError):
        await _in_uow(database, tenant_id, _activate(lost_key))
    await _in_uow(database, tenant_id, _activate(new_key))

    # DA-28: the agency is no longer on trial and shows the licence's plan.
    assert await _tenant_row(admin_engine, tenant_id) == ("active", "premium")

    # Once activated, the key can no longer be swapped.
    with pytest.raises(ConflictError):
        await _in_uow(
            database,
            tenant_id,
            lambda uow: ReplaceLicenseKeyUseCase(
                SqlAlchemyLicenseRepository(uow),  # type: ignore[arg-type]
                _HASHER,
                uow,
            ).execute(ReplaceLicenseKeyCommand(tenant_id=tenant_id)),
        )

    # A plan change follows through to the agency too.
    await _in_uow(
        database,
        tenant_id,
        lambda uow: SetLicensePlanTierUseCase(
            SqlAlchemyLicenseRepository(uow),  # type: ignore[arg-type]
            uow,
            SqlAlchemyTenantRepository(uow),  # type: ignore[arg-type]
        ).execute(SetLicensePlanTierCommand(tenant_id=tenant_id, plan_tier="basic")),
    )
    assert await _tenant_row(admin_engine, tenant_id) == ("active", "basic")
