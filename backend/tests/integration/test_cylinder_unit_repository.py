"""Integration tests for SqlAlchemyCylinderUnitRepository — round-trip, the
update path, RLS isolation, and the due-status filter (Cylinder Identity,
Phase 20 subsystem 3)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from lpg.application.common.tenant import RequestTenantContext
from lpg.domain.compliance.cylinder_unit import CylinderUnit
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.models.tenant import TenantModel  # noqa: F401
from lpg.infrastructure.persistence.repositories.compliance import (
    SqlAlchemyCylinderUnitRepository,
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
                    "VALUES (gen_random_uuid(), 'Cylinder Unit Test Co', :slug, "
                    "'ops@example.com') RETURNING id"
                ),
                {"slug": f"cyl-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
    return uuid.UUID(str(tenant_id))


async def _seed_cylinder_type_and_warehouse(
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
                    "INSERT INTO tenant.warehouse (id, tenant_id, branch_id, name, "
                    "address_line) VALUES (gen_random_uuid(), :tenant_id, :branch_id, "
                    "'Test Godown', '1 Depot Road') RETURNING id"
                ),
                {"tenant_id": str(tenant_id), "branch_id": str(branch_id)},
            )
        ).scalar_one()
        cylinder_type_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.cylinder_type (id, tenant_id, name, weight_kg) "
                    "VALUES (gen_random_uuid(), :tenant_id, '14.2kg Domestic', 14.2) "
                    "RETURNING id"
                ),
                {"tenant_id": str(tenant_id)},
            )
        ).scalar_one()
    return uuid.UUID(str(cylinder_type_id)), uuid.UUID(str(warehouse_id))


def _unit(
    tenant_id: uuid.UUID, cylinder_type_id: uuid.UUID, warehouse_id: uuid.UUID, **kw: object
) -> CylinderUnit:
    serial = str(kw.get("serial_number", f"CYL-{uuid.uuid4().hex[:8]}"))
    defaults: dict[str, object] = {
        "cylinder_unit_id": uuid.uuid4(),
        "tenant_id": tenant_id,
        "cylinder_type_id": cylinder_type_id,
        "serial_number": serial,
        "qr_code": f"CYL-{serial}",
        "condition_status": "empty",
        "custody_type": "warehouse",
        "custody_ref_id": warehouse_id,
    }
    defaults.update(kw)
    return CylinderUnit(**defaults)  # type: ignore[arg-type]


class TestCylinderUnitRepository:
    async def test_save_and_get_by_id_and_serial(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        cylinder_type_id, warehouse_id = await _seed_cylinder_type_and_warehouse(
            admin_engine, tenant_id
        )
        context = RequestTenantContext(tenant_id=tenant_id)
        unit = _unit(
            tenant_id,
            cylinder_type_id,
            warehouse_id,
            serial_number="CYL-A1",
            qr_code="CYL-A1-QR",
        )

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                await SqlAlchemyCylinderUnitRepository(uow).save(unit)

        async for verify in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(verify, context) as uow:
                repo = SqlAlchemyCylinderUnitRepository(uow)
                reloaded = await repo.get_by_id(unit.id)
                assert reloaded is not None
                assert reloaded.serial_number == "CYL-A1"
                assert reloaded.qr_code == "CYL-A1-QR"
                assert reloaded.condition_status == "empty"

                by_serial = await repo.get_by_serial("CYL-A1")
                assert by_serial is not None and by_serial.id == unit.id

                by_qr = await repo.get_by_qr_code("CYL-A1-QR")
                assert by_qr is not None and by_qr.id == unit.id

                by_lookup_qr = await repo.lookup_by_code("CYL-A1-QR")
                assert by_lookup_qr is not None and by_lookup_qr.id == unit.id

                by_lookup_serial = await repo.lookup_by_code("CYL-A1")
                assert by_lookup_serial is not None and by_lookup_serial.id == unit.id

    async def test_commands_persist_through_save(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        cylinder_type_id, warehouse_id = await _seed_cylinder_type_and_warehouse(
            admin_engine, tenant_id
        )
        context = RequestTenantContext(tenant_id=tenant_id)
        unit = _unit(tenant_id, cylinder_type_id, warehouse_id)
        performed_by = uuid.uuid4()

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                await SqlAlchemyCylinderUnitRepository(uow).save(unit)

        async for s2 in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(s2, context) as uow:
                repo = SqlAlchemyCylinderUnitRepository(uow)
                loaded = await repo.get_by_id(unit.id)
                assert loaded is not None
                loaded.record_statutory_test(
                    tested_at=datetime.now(UTC).date(),
                    due_date=datetime.now(UTC).date() + timedelta(days=730),
                    performed_by=performed_by,
                )
                loaded.receive(warehouse_id=warehouse_id, performed_by=performed_by)
                await repo.save(loaded)

        async for s3 in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(s3, context) as uow:
                final = await SqlAlchemyCylinderUnitRepository(uow).get_by_id(unit.id)
                assert final is not None
                assert final.condition_status == "filled"
                assert final.custody_type == "warehouse"
                assert final.last_tested_at is not None

    async def test_rls_hides_another_tenants_units(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_a = await _seed_tenant(admin_engine)
        cylinder_type_a, warehouse_a = await _seed_cylinder_type_and_warehouse(
            admin_engine, tenant_a
        )
        tenant_b = await _seed_tenant(admin_engine)
        unit = _unit(tenant_a, cylinder_type_a, warehouse_a)

        async for session in database.open_session(tenant_id=tenant_a):
            async with SqlAlchemyUnitOfWork(
                session, RequestTenantContext(tenant_id=tenant_a)
            ) as uow:
                await SqlAlchemyCylinderUnitRepository(uow).save(unit)

        async for other in database.open_session(tenant_id=tenant_b):
            async with SqlAlchemyUnitOfWork(other, RequestTenantContext(tenant_id=tenant_b)) as uow:
                assert await SqlAlchemyCylinderUnitRepository(uow).get_by_id(unit.id) is None
                assert (
                    await SqlAlchemyCylinderUnitRepository(uow).get_by_serial(unit.serial_number)
                    is None
                )

    async def test_list_for_tenant_due_status_filter(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        cylinder_type_id, warehouse_id = await _seed_cylinder_type_and_warehouse(
            admin_engine, tenant_id
        )
        context = RequestTenantContext(tenant_id=tenant_id)
        today = datetime.now(UTC).date()
        soon = _unit(
            tenant_id,
            cylinder_type_id,
            warehouse_id,
            serial_number="CYL-SOON",
            test_due_date=today + timedelta(days=10),
        )
        far = _unit(
            tenant_id,
            cylinder_type_id,
            warehouse_id,
            serial_number="CYL-FAR",
            test_due_date=today + timedelta(days=400),
        )
        overdue = _unit(
            tenant_id,
            cylinder_type_id,
            warehouse_id,
            serial_number="CYL-OVERDUE",
            test_due_date=today - timedelta(days=5),
        )
        never_tested = _unit(
            tenant_id, cylinder_type_id, warehouse_id, serial_number="CYL-NEVER", test_due_date=None
        )

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repo = SqlAlchemyCylinderUnitRepository(uow)
                for unit in (soon, far, overdue, never_tested):
                    await repo.save(unit)

        async for s2 in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(s2, context) as uow:
                repo = SqlAlchemyCylinderUnitRepository(uow)
                due_soon = await repo.list_for_tenant(due_status="due_soon")
                assert [u.id for u in due_soon] == [soon.id]

                overdue_list = await repo.list_for_tenant(due_status="overdue")
                assert [u.id for u in overdue_list] == [overdue.id]

                total = await repo.count_for_tenant()
                assert total == 4

    async def test_list_for_tenant_excludes_retired_units(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        cylinder_type_id, warehouse_id = await _seed_cylinder_type_and_warehouse(
            admin_engine, tenant_id
        )
        context = RequestTenantContext(tenant_id=tenant_id)
        unit = _unit(tenant_id, cylinder_type_id, warehouse_id)

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                await SqlAlchemyCylinderUnitRepository(uow).save(unit)

        async for s2 in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(s2, context) as uow:
                repo = SqlAlchemyCylinderUnitRepository(uow)
                loaded = await repo.get_by_id(unit.id)
                assert loaded is not None
                loaded.retire(performed_by=uuid.uuid4())
                await repo.save(loaded)

        async for s3 in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(s3, context) as uow:
                repo = SqlAlchemyCylinderUnitRepository(uow)
                assert await repo.list_for_tenant() == []
                assert await repo.count_for_tenant() == 0
                # Still individually reachable by id/serial — Rule 27's
                # lifetime-record requirement.
                still_reachable = await repo.get_by_id(unit.id)
                assert still_reachable is not None
                assert still_reachable.is_retired is True
