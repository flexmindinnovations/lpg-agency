"""Repository-level proof that `cylinder_ledger` stays in lockstep with
`cylinder_ledger_transaction` across a sequence of operations.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from lpg.application.common.tenant import RequestTenantContext
from lpg.domain.cylinder_ledger.cylinder_ledger import CylinderLedger
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.repositories.cylinder_ledger import (
    SqlAlchemyCylinderLedgerRepository,
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
        pytest.skip("PostgreSQL is not reachable")
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
                    "VALUES (gen_random_uuid(), 'Ledger Test Co', :slug, 'ledger@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"ledger-{uuid.uuid4().hex[:10]}"},
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


async def _seed_branch(admin_engine: AsyncEngine, *, tenant_id: uuid.UUID) -> uuid.UUID:
    async with admin_engine.begin() as conn:
        branch_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.branch (id, tenant_id, name) "
                    "VALUES (gen_random_uuid(), :tenant_id, 'Ledger Branch') RETURNING id"
                ),
                {"tenant_id": str(tenant_id)},
            )
        ).scalar_one()
    return uuid.UUID(str(branch_id))


async def _seed_customer(
    admin_engine: AsyncEngine, *, tenant_id: uuid.UUID, branch_id: uuid.UUID
) -> uuid.UUID:
    async with admin_engine.begin() as conn:
        customer_id = (
            await conn.execute(
                text(
                    "INSERT INTO customer.customer (id, tenant_id, branch_id, consumer_number, "
                    "full_name, phone_number, customer_type, status, kyc_status) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, 'C-1234', 'John Doe', "
                    "'555-1234', 'domestic', 'active', 'verified') RETURNING id"
                ),
                {"tenant_id": str(tenant_id), "branch_id": str(branch_id)},
            )
        ).scalar_one()
    return uuid.UUID(str(customer_id))


async def _count_transactions(admin_engine: AsyncEngine, *, ledger_id: uuid.UUID) -> int:
    async with admin_engine.begin() as conn:
        result = await conn.execute(
            text(
                "SELECT COUNT(*) FROM cylinder_ledger.ledger_transaction "
                "WHERE cylinder_ledger_id = :ledger_id"
            ),
            {"ledger_id": str(ledger_id)},
        )
        return int(result.scalar_one())


class TestCylinderLedgerProjectionStaysInLockstep:
    async def test_balance_matches_domain_state_after_a_mixed_sequence(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        branch_id = await _seed_branch(admin_engine, tenant_id=tenant_id)
        cylinder_type_id = await _seed_cylinder_type(admin_engine, tenant_id=tenant_id)
        customer_id = await _seed_customer(admin_engine, tenant_id=tenant_id, branch_id=branch_id)

        context = RequestTenantContext(tenant_id=tenant_id)
        ledger_id = uuid.uuid4()
        performer = uuid.uuid4()
        order_id = uuid.uuid4()

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repo = SqlAlchemyCylinderLedgerRepository(uow)
                ledger = CylinderLedger(
                    cylinder_ledger_id=ledger_id,
                    tenant_id=tenant_id,
                    customer_id=customer_id,
                )

                ledger.record_delivery(
                    cylinder_type_id,
                    2,
                    performed_by=performer,
                    reference_id=order_id,
                )

                ledger.adjust(
                    cylinder_type_id,
                    delta=-1,
                    reason="Lost one",
                    performed_by=performer,
                )
                await repo.add(ledger)

        async for session in database.open_session(tenant_id=tenant_id):
            uow = SqlAlchemyUnitOfWork(session, context)
            repo = SqlAlchemyCylinderLedgerRepository(uow)
            reloaded = await repo.get_by_customer_id(tenant_id, customer_id)
            assert reloaded is not None
            # 2 delivered - 1 lost = 1
            assert reloaded.balance_of(cylinder_type_id) == 1

        assert await _count_transactions(admin_engine, ledger_id=ledger_id) == 2
