"""`SqlAlchemyTenantRepository`, against a real PostgreSQL.

Seed rows are inserted via the elevated ``lpg_admin`` role
(``admin_engine``/``admin_conn`` fixtures) — never through the repository
itself, which cannot create rows through a tenant-scoped connection by
design (see migration ``0242df1a3871``'s docstring). This suite proves the
*read/update* half of the seam: a tenant-scoped repository sees only its own
row, and can persist a change to it.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from lpg.application.common.tenant import RequestTenantContext
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.repositories.tenant import SqlAlchemyTenantRepository
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


async def _seed_tenant(admin_engine: AsyncEngine, *, name: str, slug: str) -> uuid.UUID:
    async with admin_engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug) "
                    "VALUES (gen_random_uuid(), :name, :slug) "
                    "RETURNING id"
                ),
                {"name": name, "slug": slug},
            )
        ).scalar_one()
    # asyncpg already returns a real uuid.UUID for a `uuid` column; the
    # explicit conversion is only to satisfy mypy --strict against Core's
    # `Any`-typed raw-SQL result, not a runtime no-op.
    return uuid.UUID(str(tenant_id))


class TestGet:
    async def test_returns_the_tenants_own_row(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(
            admin_engine, name="Acme LPG", slug=f"acme-{uuid.uuid4().hex[:8]}"
        )
        context = RequestTenantContext(tenant_id=tenant_id)

        async for session in database.open_session(tenant_id=tenant_id):
            uow = SqlAlchemyUnitOfWork(session, context)
            repository = SqlAlchemyTenantRepository(uow)

            tenant = await repository.get(tenant_id)

            assert tenant is not None
            assert tenant.id == tenant_id
            assert tenant.name == "Acme LPG"

    async def test_cannot_see_another_tenants_row(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        own_id = await _seed_tenant(admin_engine, name="Own Co", slug=f"own-{uuid.uuid4().hex[:8]}")
        other_id = await _seed_tenant(
            admin_engine, name="Other Co", slug=f"other-{uuid.uuid4().hex[:8]}"
        )
        context = RequestTenantContext(tenant_id=own_id)

        async for session in database.open_session(tenant_id=own_id):
            uow = SqlAlchemyUnitOfWork(session, context)
            repository = SqlAlchemyTenantRepository(uow)

            result = await repository.get(other_id)

            assert result is None

    async def test_registers_the_loaded_aggregate_with_the_unit_of_work(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(
            admin_engine, name="Tracked Co", slug=f"tracked-{uuid.uuid4().hex[:8]}"
        )
        context = RequestTenantContext(tenant_id=tenant_id)

        async for session in database.open_session(tenant_id=tenant_id):
            uow = SqlAlchemyUnitOfWork(session, context)
            repository = SqlAlchemyTenantRepository(uow)

            tenant = await repository.get(tenant_id)
            assert tenant is not None
            tenant.rename("Renamed Co")

            events = uow.collect_events()
            assert len(events) == 1


class TestSave:
    async def test_persists_a_rename(self, database: Database, admin_engine: AsyncEngine) -> None:
        tenant_id = await _seed_tenant(
            admin_engine, name="Before Rename", slug=f"rename-{uuid.uuid4().hex[:8]}"
        )
        context = RequestTenantContext(tenant_id=tenant_id)

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repository = SqlAlchemyTenantRepository(uow)
                tenant = await repository.get(tenant_id)
                assert tenant is not None

                tenant.rename("After Rename")
                await repository.save(tenant)

        # Fresh, independently-scoped session — proves the change was
        # actually committed, not merely visible within the same transaction.
        async for verify_session in database.open_session(tenant_id=tenant_id):
            reloaded = await SqlAlchemyTenantRepository(
                SqlAlchemyUnitOfWork(verify_session, context)
            ).get(tenant_id)
            assert reloaded is not None
            assert reloaded.name == "After Rename"
