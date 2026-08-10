"""`SqlAlchemyBranchRepository`/`SqlAlchemyWarehouseRepository`, against a
real PostgreSQL — proves RLS scoping and the add/get/save round-trip, the
same pattern `test_tenant_repository.py` already established.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from lpg.application.common.tenant import RequestTenantContext
from lpg.application.tenant.branch import CreateBranchCommand, CreateBranchUseCase
from lpg.application.tenant.warehouse import CreateWarehouseCommand, CreateWarehouseUseCase
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.repositories.tenant import (
    SqlAlchemyBranchRepository,
    SqlAlchemyWarehouseRepository,
)
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
                    "VALUES (gen_random_uuid(), 'Branch Test Co', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"branch-test-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
    return uuid.UUID(str(tenant_id))


async def _seed_branch(admin_engine: AsyncEngine, *, tenant_id: uuid.UUID, name: str) -> uuid.UUID:
    async with admin_engine.begin() as conn:
        branch_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.branch (id, tenant_id, name) "
                    "VALUES (gen_random_uuid(), :tenant_id, :name) RETURNING id"
                ),
                {"tenant_id": str(tenant_id), "name": name},
            )
        ).scalar_one()
    return uuid.UUID(str(branch_id))


class TestBranchRepository:
    async def test_add_then_get_round_trips(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        context = RequestTenantContext(tenant_id=tenant_id)

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repository = SqlAlchemyBranchRepository(uow)
                use_case = CreateBranchUseCase(repository, uow)
                branch = await use_case.execute(
                    CreateBranchCommand(tenant_id=tenant_id, name="Nashik West", region="MH")
                )

        async for verify_session in database.open_session(tenant_id=tenant_id):
            reloaded = await SqlAlchemyBranchRepository(
                SqlAlchemyUnitOfWork(verify_session, context)
            ).get(branch.id)
            assert reloaded is not None
            assert reloaded.name == "Nashik West"
            assert reloaded.region == "MH"

    async def test_cannot_see_another_tenants_branch(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        own_tenant = await _seed_tenant(admin_engine)
        other_tenant = await _seed_tenant(admin_engine)
        other_branch_id = await _seed_branch(admin_engine, tenant_id=other_tenant, name="Other Co")
        context = RequestTenantContext(tenant_id=own_tenant)

        async for session in database.open_session(tenant_id=own_tenant):
            result = await SqlAlchemyBranchRepository(SqlAlchemyUnitOfWork(session, context)).get(
                other_branch_id
            )
            assert result is None

    async def test_list_for_tenant_excludes_other_tenants(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        own_tenant = await _seed_tenant(admin_engine)
        other_tenant = await _seed_tenant(admin_engine)
        await _seed_branch(admin_engine, tenant_id=own_tenant, name="Mine A")
        await _seed_branch(admin_engine, tenant_id=own_tenant, name="Mine B")
        await _seed_branch(admin_engine, tenant_id=other_tenant, name="Not Mine")
        context = RequestTenantContext(tenant_id=own_tenant)

        async for session in database.open_session(tenant_id=own_tenant):
            branches = await SqlAlchemyBranchRepository(
                SqlAlchemyUnitOfWork(session, context)
            ).list_for_tenant(own_tenant)
            names = {b.name for b in branches}
            assert names == {"Mine A", "Mine B"}


class TestWarehouseRepository:
    async def test_add_then_get_round_trips(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        branch_id = await _seed_branch(admin_engine, tenant_id=tenant_id, name="Nashik West")
        context = RequestTenantContext(tenant_id=tenant_id)

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repository = SqlAlchemyWarehouseRepository(uow)
                use_case = CreateWarehouseUseCase(repository, uow)
                warehouse = await use_case.execute(
                    CreateWarehouseCommand(
                        tenant_id=tenant_id,
                        branch_id=branch_id,
                        name="Nashik Central",
                        address_line="Plot 12, MIDC Ambad",
                    )
                )

        async for verify_session in database.open_session(tenant_id=tenant_id):
            reloaded = await SqlAlchemyWarehouseRepository(
                SqlAlchemyUnitOfWork(verify_session, context)
            ).get(warehouse.id)
            assert reloaded is not None
            assert reloaded.name == "Nashik Central"
            assert reloaded.branch_id == branch_id
