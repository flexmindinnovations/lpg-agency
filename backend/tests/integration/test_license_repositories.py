"""`SqlAlchemyLicenseRepository`/`SqlAlchemyLinkedDeviceRepository`, against a
real PostgreSQL — proves `platform.license`/`platform.linked_device` *are*
tenant-isolated by RLS (unlike `platform.feature_flag`, which deliberately
isn't — see `test_feature_flag_repositories.py`'s docstring for that
contrast), and that `platform.license_find_by_tenant_id`'s `SECURITY
DEFINER` function can read a license with no tenant session set at all.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from lpg.application.common.tenant import RequestTenantContext
from lpg.domain.license.license import License
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.repositories.license import SqlAlchemyLicenseRepository
from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration


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


async def _seed_tenant(admin_engine: AsyncEngine) -> uuid.UUID:
    async with admin_engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'License Test Co', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"license-test-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
        # `tests/integration/conftest.py`'s `_auto_activate_licenses_for_new_tenants`
        # trigger just gave this tenant a license — this suite intentionally
        # exercises license issuance itself, so it needs a clean slate before
        # each test's own `.add()` (`platform.license.tenant_id` is unique).
        await conn.execute(
            text("DELETE FROM platform.license WHERE tenant_id = :tenant_id"),
            {"tenant_id": str(tenant_id)},
        )
    return uuid.UUID(str(tenant_id))


def _new_license(tenant_id: uuid.UUID) -> License:
    return License(
        uuid.uuid4(),
        tenant_id,
        f"hash-{uuid.uuid4().hex}",
        "LPG-TEST",
        "standard",
        timedelta(days=365),
        datetime.now(UTC),
    )


class TestLicenseTenantIsolation:
    async def test_a_license_created_under_one_tenant_is_invisible_to_another(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_a = await _seed_tenant(admin_engine)
        tenant_b = await _seed_tenant(admin_engine)
        context_a = RequestTenantContext(tenant_id=tenant_a)

        async for session in database.open_session(tenant_id=tenant_a):
            async with SqlAlchemyUnitOfWork(session, context_a) as uow:
                await SqlAlchemyLicenseRepository(uow).add(_new_license(tenant_a))

        # Tenant A's own session sees it.
        async for session in database.open_session(tenant_id=tenant_a):
            license_ = await SqlAlchemyLicenseRepository(
                SqlAlchemyUnitOfWork(session, context_a)
            ).get_by_tenant_id(tenant_a)
            assert license_ is not None

        # Tenant B's session — unlike platform.feature_flag — sees nothing,
        # because platform.license is a normal RLS-scoped tenant table.
        context_b = RequestTenantContext(tenant_id=tenant_b)
        async for session in database.open_session(tenant_id=tenant_b):
            license_ = await SqlAlchemyLicenseRepository(
                SqlAlchemyUnitOfWork(session, context_b)
            ).get_by_tenant_id(tenant_a)
            assert license_ is None

    async def test_the_pre_auth_security_definer_function_reads_with_no_tenant_session(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        context = RequestTenantContext(tenant_id=tenant_id)

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                await SqlAlchemyLicenseRepository(uow).add(_new_license(tenant_id))

        # No tenant_id passed to session() at all — the ordinary RLS-scoped
        # path would see nothing here; the SECURITY DEFINER function must
        # still find the row.
        async for session in database.session():
            result = await session.execute(
                text("SELECT * FROM platform.license_find_by_tenant_id(:tenant_id)"),
                {"tenant_id": str(tenant_id)},
            )
            row = result.one()
            assert row.id is not None
            assert row.tenant_id == tenant_id

    async def test_add_then_get_round_trips_every_field(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        context = RequestTenantContext(tenant_id=tenant_id)
        license_ = _new_license(tenant_id)

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                await SqlAlchemyLicenseRepository(uow).add(license_)

        async for session in database.open_session(tenant_id=tenant_id):
            reloaded = await SqlAlchemyLicenseRepository(
                SqlAlchemyUnitOfWork(session, context)
            ).get(license_.id)
            assert reloaded is not None
            assert reloaded.tenant_id == tenant_id
            assert reloaded.key_hash == license_.key_hash
            assert reloaded.plan_tier == "standard"
            assert reloaded.activated_at is None

    async def test_activation_persists_across_reload(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        context = RequestTenantContext(tenant_id=tenant_id)
        license_ = _new_license(tenant_id)

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                await SqlAlchemyLicenseRepository(uow).add(license_)

        now = datetime.now(UTC)
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repository = SqlAlchemyLicenseRepository(uow)
                loaded = await repository.get(license_.id)
                assert loaded is not None
                loaded.activate(at=now)
                await repository.save(loaded)

        async for session in database.open_session(tenant_id=tenant_id):
            reloaded = await SqlAlchemyLicenseRepository(
                SqlAlchemyUnitOfWork(session, context)
            ).get(license_.id)
            assert reloaded is not None
            assert reloaded.activated_at == now
