"""Regression tests: `SqlAlchemyDriverRepository.save()` and
`SqlAlchemyVehicleRepository.save()`'s insert branches built the ORM row
straight from the passed-in aggregate without ever calling
`register_aggregate` — the one call that makes the UnitOfWork's
`collect_events()` see an aggregate at all. Neither `Driver` nor `Vehicle`
had a dedicated repository test file at all before this, which is exactly
how the same bug (found and fixed in `employee.py`'s `save()`, 2026-09-30)
went unnoticed here too.

`DriverRegistered` has a live subscriber
(`realtime_handlers.on_driver_updated`) — this one was a real, currently
broken feature, not just a latent gap. `VehicleRegistered` has none yet.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from lpg.application.common.tenant import RequestTenantContext
from lpg.domain.delivery.driver import Driver, DriverRegistered
from lpg.domain.delivery.vehicle import Vehicle, VehicleRegistered
from lpg.infrastructure.events.dispatcher import DomainEventDispatcher
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.models.tenant import TenantModel  # noqa: F401
from lpg.infrastructure.persistence.repositories.driver import SqlAlchemyDriverRepository
from lpg.infrastructure.persistence.repositories.vehicle import SqlAlchemyVehicleRepository
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
                    "VALUES (gen_random_uuid(), 'Driver/Vehicle Event Test Co', :slug, "
                    "'ops@example.com') RETURNING id"
                ),
                {"slug": f"driver-vehicle-events-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
    return uuid.UUID(str(tenant_id))


async def _seed_branch(admin_engine: AsyncEngine, tenant_id: uuid.UUID) -> uuid.UUID:
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
    return uuid.UUID(str(branch_id))


async def _seed_employee(
    admin_engine: AsyncEngine, tenant_id: uuid.UUID, branch_id: uuid.UUID
) -> uuid.UUID:
    async with admin_engine.begin() as conn:
        employee_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.employee "
                    "(id, tenant_id, branch_id, employee_code, first_name, last_name, "
                    "phone_number, role, status) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :code, "
                    "'Test', 'Driver', :phone, 'driver', 'active') RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id),
                    "code": f"EMP-{uuid.uuid4().hex[:8]}",
                    "phone": f"+9199{uuid.uuid4().int % 10**8:08d}",
                },
            )
        ).scalar_one()
    return uuid.UUID(str(employee_id))


class TestDriverRepositoryEvents:
    async def test_saving_a_new_driver_dispatches_driver_registered(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        branch_id = await _seed_branch(admin_engine, tenant_id)
        employee_id = await _seed_employee(admin_engine, tenant_id, branch_id)
        context = RequestTenantContext(tenant_id=tenant_id)
        driver = Driver(
            driver_id=uuid.uuid4(),
            tenant_id=tenant_id,
            branch_id=branch_id,
            employee_id=employee_id,
            license_number="PENDING",
        )

        received: list[DriverRegistered] = []

        async def _capture(event: DriverRegistered) -> None:
            received.append(event)

        dispatcher = DomainEventDispatcher()
        dispatcher.register(DriverRegistered, _capture)  # type: ignore[arg-type]

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context, event_dispatcher=dispatcher) as uow:
                await SqlAlchemyDriverRepository(uow).save(driver)

        assert [e.driver_id for e in received] == [driver.id]

        async for verify in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(verify, context) as uow:
                reloaded = await SqlAlchemyDriverRepository(uow).get_by_id(driver.id)
                assert reloaded is not None
                assert reloaded.employee_id == employee_id


class TestVehicleRepositoryEvents:
    async def test_saving_a_new_vehicle_dispatches_vehicle_registered(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        branch_id = await _seed_branch(admin_engine, tenant_id)
        context = RequestTenantContext(tenant_id=tenant_id)
        vehicle = Vehicle(
            vehicle_id=uuid.uuid4(),
            tenant_id=tenant_id,
            branch_id=branch_id,
            registration_number=f"TS-{uuid.uuid4().hex[:6].upper()}",
            make="Tata",
            model="Ace",
            capacity_units=20,
        )

        received: list[VehicleRegistered] = []

        async def _capture(event: VehicleRegistered) -> None:
            received.append(event)

        dispatcher = DomainEventDispatcher()
        dispatcher.register(VehicleRegistered, _capture)  # type: ignore[arg-type]

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context, event_dispatcher=dispatcher) as uow:
                await SqlAlchemyVehicleRepository(uow).save(vehicle)

        assert [e.vehicle_id for e in received] == [vehicle.id]

        async for verify in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(verify, context) as uow:
                reloaded = await SqlAlchemyVehicleRepository(uow).get_by_id(vehicle.id)
                assert reloaded is not None
                assert reloaded.registration_number == vehicle.registration_number
