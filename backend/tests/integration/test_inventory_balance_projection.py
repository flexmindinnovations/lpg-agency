"""Repository-level proof that `inventory_balance` stays in lockstep with
`inventory_transaction` across a sequence of operations, plus an RLS
cross-tenant isolation check specific to `inventory_location`'s polymorphic
`location_ref_id` (no physical FK — `docs/data/03-database-schema.md`'s own
flagged risk, worth its own explicit proof).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from lpg.application.common.tenant import RequestTenantContext
from lpg.domain.inventory.inventory_location import InventoryLocation
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.repositories.inventory import (
    SqlAlchemyInventoryLocationRepository,
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
                    "VALUES (gen_random_uuid(), 'Inventory Test Co', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"inv-test-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
    return uuid.UUID(str(tenant_id))


async def _seed_cylinder_type(admin_engine: AsyncEngine, *, tenant_id: uuid.UUID) -> uuid.UUID:
    async with admin_engine.begin() as conn:
        cylinder_type_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.cylinder_type (id, tenant_id, name, weight_kg) "
                    "VALUES (gen_random_uuid(), :tenant_id, '14.2kg', 14.2) RETURNING id"
                ),
                {"tenant_id": str(tenant_id)},
            )
        ).scalar_one()
    return uuid.UUID(str(cylinder_type_id))


async def _count_transactions(admin_engine: AsyncEngine, *, location_id: uuid.UUID) -> int:
    async with admin_engine.begin() as conn:
        result = await conn.execute(
            text(
                "SELECT COUNT(*) FROM inventory.inventory_transaction "
                "WHERE inventory_location_id = :location_id"
            ),
            {"location_id": str(location_id)},
        )
        return int(result.scalar_one())


class TestBalanceProjectionStaysInLockstep:
    async def test_balance_matches_domain_state_after_a_mixed_sequence(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        cylinder_type_id = await _seed_cylinder_type(admin_engine, tenant_id=tenant_id)
        context = RequestTenantContext(tenant_id=tenant_id)
        location_id = uuid.uuid4()
        performer = uuid.uuid4()

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repo = SqlAlchemyInventoryLocationRepository(uow)
                location = InventoryLocation(
                    inventory_location_id=location_id,
                    tenant_id=tenant_id,
                    location_type="warehouse",
                    location_ref_id=uuid.uuid4(),
                )
                location.receive_goods(cylinder_type_id, 100, performed_by=performer)
                location.unload(cylinder_type_id, "filled", 30, performed_by=performer)
                await repo.save(location)

        async for session in database.open_session(tenant_id=tenant_id):
            uow = SqlAlchemyUnitOfWork(session, context)
            repo = SqlAlchemyInventoryLocationRepository(uow)
            reloaded = await repo.get_by_id(location_id)
            assert reloaded is not None
            assert reloaded.balance_of(cylinder_type_id, "filled") == 70

        assert await _count_transactions(admin_engine, location_id=location_id) == 2

        # A second save() touching the same status pair again — proves the
        # projection reads the ORM row and updates it (not just inserts a
        # duplicate) across separate transactions, not only within one.
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repo = SqlAlchemyInventoryLocationRepository(uow)
                location = await repo.get_by_id(location_id)
                assert location is not None
                location.change_status(
                    cylinder_type_id, "filled", "leakage", 10, performed_by=performer
                )
                await repo.save(location)

        async for session in database.open_session(tenant_id=tenant_id):
            uow = SqlAlchemyUnitOfWork(session, context)
            repo = SqlAlchemyInventoryLocationRepository(uow)
            reloaded = await repo.get_by_id(location_id)
            assert reloaded is not None
            assert reloaded.balance_of(cylinder_type_id, "filled") == 60
            assert reloaded.balance_of(cylinder_type_id, "leakage") == 10

            page = await repo.list_transactions(location_id)
            assert len(page.items) == 3
            assert {item.transaction_type for item in page.items} == {
                "grn_receipt",
                "unload",
                "status_change",
            }

        assert await _count_transactions(admin_engine, location_id=location_id) == 3


class TestCrossTenantIsolation:
    async def test_cannot_see_another_tenants_inventory_location(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        """`location_ref_id` has no physical FK (polymorphic warehouse/vehicle
        reference, accepted risk per `03-database-schema.md`) — RLS on
        `tenant_id` is the only thing preventing cross-tenant access, so it
        gets its own explicit proof rather than relying on other tables'
        FK-adjacent RLS tests to imply it works here too.
        """
        tenant_1 = await _seed_tenant(admin_engine)
        tenant_2 = await _seed_tenant(admin_engine)
        cylinder_type_id = await _seed_cylinder_type(admin_engine, tenant_id=tenant_1)

        location_id = uuid.uuid4()
        context_1 = RequestTenantContext(tenant_id=tenant_1)
        async for session in database.open_session(tenant_id=tenant_1):
            async with SqlAlchemyUnitOfWork(session, context_1) as uow:
                repo = SqlAlchemyInventoryLocationRepository(uow)
                location = InventoryLocation(
                    inventory_location_id=location_id,
                    tenant_id=tenant_1,
                    location_type="warehouse",
                    location_ref_id=uuid.uuid4(),
                )
                location.receive_goods(cylinder_type_id, 10, performed_by=uuid.uuid4())
                await repo.save(location)

        context_2 = RequestTenantContext(tenant_id=tenant_2)
        async for session in database.open_session(tenant_id=tenant_2):
            uow = SqlAlchemyUnitOfWork(session, context_2)
            repo = SqlAlchemyInventoryLocationRepository(uow)
            reloaded = await repo.get_by_id(location_id)
            assert reloaded is None  # RLS filters it out
