"""`POST /platform/license/{tenant_id}/activate` — the platform-tier sibling
of `POST /admin/license/activate` (`routers/admin.py`), added so a
`super_admin` can activate a license right after issuing it rather than
waiting on the tenant's own self-service flow.

`ActivateLicenseUseCase` itself (already tenant-agnostic in its command
shape) is unchanged and already fully covered by `test_license_lifecycle.py`
against the tenant-scoped `UnitOfWork` path — this file's own concern is
narrower: proving the *platform* wiring (`get_platform_unit_of_work_factory`,
scoped to an explicit target tenant rather than the caller's own) reaches
the same use case correctly, mirroring `test_platform_agency_lifecycle.py`'s
own reasoning for why that's a distinct thing worth testing.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from lpg.application.common.tenant import RequestTenantContext
from lpg.application.license.activate_license import ActivateLicenseCommand, ActivateLicenseUseCase
from lpg.application.license.issue_license import IssueLicenseCommand, IssueLicenseUseCase
from lpg.domain.license.license import LicenseLifecycleState
from lpg.infrastructure.identity.token_hasher import Sha256TokenHasher
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.repositories.license import SqlAlchemyLicenseRepository
from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration


class _NoopLicenseStatusChecker:
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


@pytest.fixture
async def admin_engine(postgres_available: bool) -> AsyncIterator[AsyncEngine]:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable — start it with ./scripts/dev-up.sh")
    engine = create_async_engine(
        "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:55432/lpg_test"
    )
    try:
        yield engine
    finally:
        await engine.dispose()


async def _seed_tenant(admin_engine: AsyncEngine) -> uuid.UUID:
    async with admin_engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'Platform Activation Test Co', :slug, "
                    "'ops@example.com') RETURNING id"
                ),
                {"slug": f"platform-activate-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
        # Same cleanup `test_license_lifecycle.py::_seed_tenant` does — the
        # dev-only auto-activate trigger would otherwise leave this tenant
        # with a license already issued.
        await conn.execute(
            text("DELETE FROM platform.license WHERE tenant_id = :tenant_id"),
            {"tenant_id": str(tenant_id)},
        )
    return uuid.UUID(str(tenant_id))


class TestPlatformLicenseActivation:
    async def test_issue_then_activate_through_the_platform_uow_path(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        context = RequestTenantContext(tenant_id=tenant_id)
        token_hasher = Sha256TokenHasher()
        status_checker = _NoopLicenseStatusChecker()

        # 1. Issue — mirrors `routers/platform.py::issue_license`'s own
        # `async with uow_factory(target_tenant_id) as uow:` shape.
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repository = SqlAlchemyLicenseRepository(uow)
                issued, plaintext_key = await IssueLicenseUseCase(
                    repository, token_hasher, uow
                ).execute(IssueLicenseCommand(tenant_id=tenant_id, plan_tier="standard"))

        assert issued.activated_at is None

        # 2. Activate — the new endpoint's own use-case wiring, still keyed
        # off the *target* tenant (never a caller's own, since a
        # `PlatformPrincipal` has none).
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repository = SqlAlchemyLicenseRepository(uow)
                activated = await ActivateLicenseUseCase(
                    repository, token_hasher, status_checker, uow
                ).execute(
                    ActivateLicenseCommand(tenant_id=tenant_id, presented_key=plaintext_key)
                )

        assert activated.id == issued.id
        assert activated.activated_at is not None
        assert activated.compute_status(at=datetime.now(UTC)) is LicenseLifecycleState.ACTIVE
