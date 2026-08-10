"""`SqlAlchemyCylinderTypeRepository`, against a real PostgreSQL."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from lpg.application.common.tenant import RequestTenantContext
from lpg.application.tenant.cylinder_type import (
    CreateCylinderTypeCommand,
    CreateCylinderTypeUseCase,
)
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.repositories.tenant import SqlAlchemyCylinderTypeRepository
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
                    "VALUES (gen_random_uuid(), 'Cylinder Test Co', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"cyl-test-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
    return uuid.UUID(str(tenant_id))


class TestCylinderTypeRepository:
    async def test_add_then_get_round_trips(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        context = RequestTenantContext(tenant_id=tenant_id)

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repository = SqlAlchemyCylinderTypeRepository(uow)
                use_case = CreateCylinderTypeUseCase(repository, uow)
                cylinder_type = await use_case.execute(
                    CreateCylinderTypeCommand(
                        tenant_id=tenant_id, name="14.2kg Domestic", weight_kg=Decimal("14.20")
                    )
                )

        async for verify_session in database.open_session(tenant_id=tenant_id):
            reloaded = await SqlAlchemyCylinderTypeRepository(
                SqlAlchemyUnitOfWork(verify_session, context)
            ).get(cylinder_type.id)
            assert reloaded is not None
            assert reloaded.name == "14.2kg Domestic"
            assert reloaded.weight_kg == Decimal("14.20")
            assert reloaded.is_active is True

    async def test_the_weight_positive_check_constraint_is_enforced_at_the_database_too(
        self, postgres_available: bool, admin_engine: AsyncEngine
    ) -> None:
        if not postgres_available:
            pytest.skip("PostgreSQL is not reachable — start it with ./scripts/dev-up.sh")
        tenant_id = await _seed_tenant(admin_engine)

        with pytest.raises(Exception, match="ck_cylinder_type_weight_positive"):
            async with admin_engine.begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO tenant.cylinder_type (id, tenant_id, name, weight_kg) "
                        "VALUES (gen_random_uuid(), :tenant_id, 'Bad', 0)"
                    ),
                    {"tenant_id": str(tenant_id)},
                )

    async def test_name_is_unique_per_tenant(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        context = RequestTenantContext(tenant_id=tenant_id)

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                use_case = CreateCylinderTypeUseCase(SqlAlchemyCylinderTypeRepository(uow), uow)
                await use_case.execute(
                    CreateCylinderTypeCommand(
                        tenant_id=tenant_id, name="14.2kg Domestic", weight_kg=Decimal("14.20")
                    )
                )

        with pytest.raises(Exception, match="uq_cylinder_type_tenant_name"):
            async for session in database.open_session(tenant_id=tenant_id):
                async with SqlAlchemyUnitOfWork(session, context) as uow:
                    use_case = CreateCylinderTypeUseCase(SqlAlchemyCylinderTypeRepository(uow), uow)
                    await use_case.execute(
                        CreateCylinderTypeCommand(
                            tenant_id=tenant_id, name="14.2kg Domestic", weight_kg=Decimal("19.00")
                        )
                    )
