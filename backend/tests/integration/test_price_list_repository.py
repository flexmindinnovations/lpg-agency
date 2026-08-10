"""`SqlAlchemyPriceListRepository`, against a real PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from lpg.application.common.tenant import RequestTenantContext
from lpg.application.tenant.price_list import (
    GetEffectivePriceQuery,
    GetEffectivePriceUseCase,
    SetPriceCommand,
    SetPriceUseCase,
)
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.repositories.tenant import SqlAlchemyPriceListRepository
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
                    "VALUES (gen_random_uuid(), 'Price Test Co', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"price-test-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
    return uuid.UUID(str(tenant_id))


async def _seed_cylinder_type(admin_engine: AsyncEngine, *, tenant_id: uuid.UUID) -> uuid.UUID:
    async with admin_engine.begin() as conn:
        cylinder_type_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.cylinder_type (id, tenant_id, name, weight_kg) "
                    "VALUES (gen_random_uuid(), :tenant_id, '14.2kg Domestic', 14.20) "
                    "RETURNING id"
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
                    "VALUES (gen_random_uuid(), :tenant_id, 'Nashik West') RETURNING id"
                ),
                {"tenant_id": str(tenant_id)},
            )
        ).scalar_one()
    return uuid.UUID(str(branch_id))


class TestSetAndResolvePrice:
    async def test_a_branch_override_wins_over_the_tenant_wide_default(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        cylinder_type_id = await _seed_cylinder_type(admin_engine, tenant_id=tenant_id)
        branch_id = await _seed_branch(admin_engine, tenant_id=tenant_id)
        context = RequestTenantContext(tenant_id=tenant_id)
        now = datetime.now(UTC)

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                use_case = SetPriceUseCase(SqlAlchemyPriceListRepository(uow), uow)
                await use_case.execute(
                    SetPriceCommand(
                        tenant_id=tenant_id,
                        cylinder_type_id=cylinder_type_id,
                        customer_type="domestic",
                        price=Decimal("900.00"),
                        effective_from=now - timedelta(days=10),
                    )
                )
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                use_case = SetPriceUseCase(SqlAlchemyPriceListRepository(uow), uow)
                await use_case.execute(
                    SetPriceCommand(
                        tenant_id=tenant_id,
                        cylinder_type_id=cylinder_type_id,
                        customer_type="domestic",
                        price=Decimal("850.00"),
                        branch_id=branch_id,
                        effective_from=now - timedelta(days=1),
                    )
                )

        async for session in database.open_session(tenant_id=tenant_id):
            query_use_case = GetEffectivePriceUseCase(
                SqlAlchemyPriceListRepository(SqlAlchemyUnitOfWork(session, context))
            )
            effective = await query_use_case.execute(
                GetEffectivePriceQuery(
                    tenant_id=tenant_id,
                    cylinder_type_id=cylinder_type_id,
                    customer_type="domestic",
                    branch_id=branch_id,
                    at=now,
                )
            )
            assert effective is not None
            assert effective.price == Decimal("850.00")

            # A different branch, with no override of its own, still falls
            # back to the tenant-wide default.
            other_branch_effective = await query_use_case.execute(
                GetEffectivePriceQuery(
                    tenant_id=tenant_id,
                    cylinder_type_id=cylinder_type_id,
                    customer_type="domestic",
                    branch_id=uuid.uuid4(),
                    at=now,
                )
            )
            assert other_branch_effective is not None
            assert other_branch_effective.price == Decimal("900.00")

    async def test_the_positive_price_check_constraint_is_enforced_at_the_database_too(
        self, postgres_available: bool, admin_engine: AsyncEngine
    ) -> None:
        if not postgres_available:
            pytest.skip("PostgreSQL is not reachable — start it with ./scripts/dev-up.sh")
        tenant_id = await _seed_tenant(admin_engine)
        cylinder_type_id = await _seed_cylinder_type(admin_engine, tenant_id=tenant_id)

        with pytest.raises(Exception, match="ck_price_list_price_positive"):
            async with admin_engine.begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO tenant.price_list "
                        "(id, tenant_id, cylinder_type_id, customer_type, price, effective_from) "
                        "VALUES (gen_random_uuid(), :tenant_id, :cylinder_type_id, 'domestic', "
                        "0, now())"
                    ),
                    {"tenant_id": str(tenant_id), "cylinder_type_id": str(cylinder_type_id)},
                )
