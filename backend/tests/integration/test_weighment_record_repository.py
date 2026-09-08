"""Integration tests for SqlAlchemyWeighmentRecordRepository — add, list by
reference, latest-passing lookup, RLS isolation, and the DB-level
append-only enforcement (Weighment Part 2)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from lpg.application.common.tenant import RequestTenantContext
from lpg.domain.compliance.scale import Scale
from lpg.domain.compliance.weighment_record import WeighmentRecord
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.models.tenant import TenantModel  # noqa: F401
from lpg.infrastructure.persistence.repositories.compliance import (
    SqlAlchemyScaleRepository,
    SqlAlchemyWeighmentRecordRepository,
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
                    "VALUES (gen_random_uuid(), 'Weighment Test Co', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"wt-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
    return uuid.UUID(str(tenant_id))


async def _seed_warehouse_and_cylinder_type(
    admin_engine: AsyncEngine, tenant_id: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID]:
    async with admin_engine.begin() as conn:
        branch_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.branch (id, tenant_id, name) "
                    "VALUES (gen_random_uuid(), :tenant_id, 'Test Branch') RETURNING id"
                ),
                {"tenant_id": str(tenant_id)},
            )
        ).scalar_one()
        warehouse_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.warehouse (id, tenant_id, branch_id, name, address_line) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, 'Test Godown', "
                    "'1 Depot Road') RETURNING id"
                ),
                {"tenant_id": str(tenant_id), "branch_id": str(branch_id)},
            )
        ).scalar_one()
        cylinder_type_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.cylinder_type (id, tenant_id, name, weight_kg) "
                    "VALUES (gen_random_uuid(), :tenant_id, '14.2kg Domestic', 14.2) RETURNING id"
                ),
                {"tenant_id": str(tenant_id)},
            )
        ).scalar_one()
    return uuid.UUID(str(warehouse_id)), uuid.UUID(str(cylinder_type_id))


def _record(
    tenant_id: uuid.UUID,
    scale_id: uuid.UUID,
    cylinder_type_id: uuid.UUID,
    reference_id: uuid.UUID,
    **kw: object,
) -> WeighmentRecord:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "tenant_id": tenant_id,
        "scale_id": scale_id,
        "context": "goods_receipt_sample",
        "reference_type": "grn",
        "reference_id": reference_id,
        "cylinder_type_id": cylinder_type_id,
        "total_cylinders_in_batch": 100,
        "cylinders_checked": 10,
        "underweight_cylinder_count": 0,
        "tolerance_grams_applied": 150,
        "result": "pass",
        "recorded_by": uuid.uuid4(),
        "recorded_at": datetime.now(UTC),
    }
    defaults.update(kw)
    return WeighmentRecord(**defaults)  # type: ignore[arg-type]


class TestWeighmentRecordRepository:
    async def test_add_and_list_for_reference(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        warehouse_id, cylinder_type_id = await _seed_warehouse_and_cylinder_type(
            admin_engine, tenant_id
        )
        context = RequestTenantContext(tenant_id=tenant_id)
        grn_id = uuid.uuid4()

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                scale = Scale(
                    scale_id=SqlAlchemyScaleRepository(uow).next_id(),
                    tenant_id=tenant_id,
                    warehouse_id=warehouse_id,
                    asset_tag="SCALE-REC-1",
                    least_count_grams=10,
                    certificate_ref="tenant/x/compliance-staging/cert.pdf",
                    certificate_expiry_date=datetime.now(UTC).date(),
                )
                await SqlAlchemyScaleRepository(uow).save(scale)
                scale_id = scale.id

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repo = SqlAlchemyWeighmentRecordRepository(uow)
                record = _record(tenant_id, scale_id, cylinder_type_id, grn_id)
                await repo.add(record)

        async for verify in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(verify, context) as uow:
                repo = SqlAlchemyWeighmentRecordRepository(uow)
                listed = await repo.list_for_reference("grn", grn_id)
                assert [r.id for r in listed] == [record.id]
                assert listed[0].result == "pass"

    async def test_get_latest_passing_for_reference_ignores_failed_records(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        warehouse_id, cylinder_type_id = await _seed_warehouse_and_cylinder_type(
            admin_engine, tenant_id
        )
        context = RequestTenantContext(tenant_id=tenant_id)
        route_id = uuid.uuid4()

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                scale = Scale(
                    scale_id=SqlAlchemyScaleRepository(uow).next_id(),
                    tenant_id=tenant_id,
                    warehouse_id=warehouse_id,
                    asset_tag="SCALE-REC-2",
                    least_count_grams=10,
                    certificate_ref="tenant/x/compliance-staging/cert.pdf",
                    certificate_expiry_date=datetime.now(UTC).date(),
                )
                await SqlAlchemyScaleRepository(uow).save(scale)
                scale_id = scale.id

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repo = SqlAlchemyWeighmentRecordRepository(uow)
                failed = _record(
                    tenant_id,
                    scale_id,
                    cylinder_type_id,
                    route_id,
                    context="load_out_full_check",
                    reference_type="route",
                    total_cylinders_in_batch=50,
                    cylinders_checked=50,
                    underweight_cylinder_count=2,
                    result="fail",
                )
                await repo.add(failed)

        async for check in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(check, context) as uow:
                repo = SqlAlchemyWeighmentRecordRepository(uow)
                none_yet = await repo.get_latest_passing_for_reference(
                    "route", route_id, context="load_out_full_check"
                )
                assert none_yet is None

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repo = SqlAlchemyWeighmentRecordRepository(uow)
                passing = _record(
                    tenant_id,
                    scale_id,
                    cylinder_type_id,
                    route_id,
                    context="load_out_full_check",
                    reference_type="route",
                    total_cylinders_in_batch=50,
                    cylinders_checked=50,
                    underweight_cylinder_count=0,
                    result="pass",
                )
                await repo.add(passing)

        async for check2 in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(check2, context) as uow:
                repo = SqlAlchemyWeighmentRecordRepository(uow)
                found = await repo.get_latest_passing_for_reference(
                    "route", route_id, context="load_out_full_check"
                )
                assert found is not None
                assert found.id == passing.id

    async def test_rls_hides_another_tenants_records(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_a = await _seed_tenant(admin_engine)
        warehouse_a, cylinder_type_a = await _seed_warehouse_and_cylinder_type(
            admin_engine, tenant_a
        )
        tenant_b = await _seed_tenant(admin_engine)
        grn_id = uuid.uuid4()

        async for session in database.open_session(tenant_id=tenant_a):
            async with SqlAlchemyUnitOfWork(
                session, RequestTenantContext(tenant_id=tenant_a)
            ) as uow:
                scale = Scale(
                    scale_id=SqlAlchemyScaleRepository(uow).next_id(),
                    tenant_id=tenant_a,
                    warehouse_id=warehouse_a,
                    asset_tag="SCALE-REC-3",
                    least_count_grams=10,
                    certificate_ref="tenant/x/compliance-staging/cert.pdf",
                    certificate_expiry_date=datetime.now(UTC).date(),
                )
                await SqlAlchemyScaleRepository(uow).save(scale)
                scale_id = scale.id

        async for session in database.open_session(tenant_id=tenant_a):
            async with SqlAlchemyUnitOfWork(
                session, RequestTenantContext(tenant_id=tenant_a)
            ) as uow:
                await SqlAlchemyWeighmentRecordRepository(uow).add(
                    _record(tenant_a, scale_id, cylinder_type_a, grn_id)
                )

        async for other in database.open_session(tenant_id=tenant_b):
            async with SqlAlchemyUnitOfWork(other, RequestTenantContext(tenant_id=tenant_b)) as uow:
                hidden = await SqlAlchemyWeighmentRecordRepository(uow).list_for_reference(
                    "grn", grn_id
                )
                assert hidden == []

    async def test_the_app_role_cannot_update_a_weighment_record(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        """DB-level append-only enforcement — the migration REVOKEs UPDATE/
        DELETE from the app role, so even a bug that tried to mutate a row
        would fail loudly, not silently succeed."""
        tenant_id = await _seed_tenant(admin_engine)
        warehouse_id, cylinder_type_id = await _seed_warehouse_and_cylinder_type(
            admin_engine, tenant_id
        )
        context = RequestTenantContext(tenant_id=tenant_id)
        grn_id = uuid.uuid4()

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                scale = Scale(
                    scale_id=SqlAlchemyScaleRepository(uow).next_id(),
                    tenant_id=tenant_id,
                    warehouse_id=warehouse_id,
                    asset_tag="SCALE-REC-4",
                    least_count_grams=10,
                    certificate_ref="tenant/x/compliance-staging/cert.pdf",
                    certificate_expiry_date=datetime.now(UTC).date(),
                )
                await SqlAlchemyScaleRepository(uow).save(scale)
                scale_id = scale.id

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                record = _record(tenant_id, scale_id, cylinder_type_id, grn_id)
                await SqlAlchemyWeighmentRecordRepository(uow).add(record)

        async for attempt in database.open_session(tenant_id=tenant_id):
            with pytest.raises(DBAPIError, match="permission denied"):
                await attempt.execute(
                    text("UPDATE compliance.weighment_record SET result = 'fail' WHERE id = :id"),
                    {"id": str(record.id)},
                )
                await attempt.commit()
