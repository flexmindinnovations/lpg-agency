"""Integration tests for the Cylinder Identity application use cases
(Phase 20 subsystem 3) against real Postgres — the Rule-26 `receive()`
block end to end, the tenant-config prefill-suggestion, and duplicate-serial
rejection."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from lpg.application.common.errors import (
    CylinderDueForStatutoryTestError,
    DuplicateCylinderSerialNumberError,
)
from lpg.application.common.tenant import RequestTenantContext
from lpg.application.compliance.use_cases import (
    ReceiveCylinderUnitCommand,
    ReceiveCylinderUnitUseCase,
    RegisterCylinderUnitCommand,
    RegisterCylinderUnitUseCase,
    SuggestStatutoryTestDueDateQuery,
    SuggestStatutoryTestDueDateUseCase,
)
from lpg.domain.tenant.tenant_configuration import TenantConfiguration
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.models.tenant import TenantModel  # noqa: F401
from lpg.infrastructure.persistence.repositories.compliance import (
    SqlAlchemyCylinderUnitRepository,
)
from lpg.infrastructure.persistence.repositories.tenant import (
    SqlAlchemyTenantConfigurationRepository,
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
                    "VALUES (gen_random_uuid(), 'Cylinder Unit UC Test Co', :slug, "
                    "'ops@example.com') RETURNING id"
                ),
                {"slug": f"cyluc-{uuid.uuid4().hex[:10]}"},
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


class TestRegisterCylinderUnit:
    async def test_registers_and_rejects_a_duplicate_serial(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        cylinder_type_id, warehouse_id = await _seed_cylinder_type_and_warehouse(
            admin_engine, tenant_id
        )
        context = RequestTenantContext(tenant_id=tenant_id)

        command = RegisterCylinderUnitCommand(
            tenant_id=tenant_id,
            cylinder_type_id=cylinder_type_id,
            serial_number="CYL-DUP-001",
            condition_status="empty",
            custody_type="warehouse",
            custody_ref_id=warehouse_id,
        )

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                use_case = RegisterCylinderUnitUseCase(SqlAlchemyCylinderUnitRepository(uow), uow)
                await use_case.execute(command)

        async for s2 in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(s2, context) as uow:
                use_case = RegisterCylinderUnitUseCase(SqlAlchemyCylinderUnitRepository(uow), uow)
                with pytest.raises(DuplicateCylinderSerialNumberError):
                    await use_case.execute(command)


class TestReceiveCylinderUnit:
    async def test_blocks_receiving_a_unit_that_is_due_for_test(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        cylinder_type_id, warehouse_id = await _seed_cylinder_type_and_warehouse(
            admin_engine, tenant_id
        )
        context = RequestTenantContext(tenant_id=tenant_id)
        today = datetime.now(UTC).date()

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repo = SqlAlchemyCylinderUnitRepository(uow)
                registered = await RegisterCylinderUnitUseCase(repo, uow).execute(
                    RegisterCylinderUnitCommand(
                        tenant_id=tenant_id,
                        cylinder_type_id=cylinder_type_id,
                        serial_number="CYL-OVERDUE-001",
                        condition_status="empty",
                        custody_type="warehouse",
                        custody_ref_id=warehouse_id,
                    )
                )
                unit_id = registered.id

        # A separate uow — `commit()` is idempotent-after-first-call, so the
        # register use case's own internal commit above must not be reused
        # for this second mutation.
        async for s2 in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(s2, context) as uow:
                repo = SqlAlchemyCylinderUnitRepository(uow)
                loaded = await repo.get_by_id(unit_id)
                assert loaded is not None
                loaded.record_statutory_test(
                    tested_at=today - timedelta(days=800),
                    due_date=today - timedelta(days=5),  # overdue
                    performed_by=uuid.uuid4(),
                )
                await repo.save(loaded)

        async for s3 in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(s3, context) as uow:
                use_case = ReceiveCylinderUnitUseCase(SqlAlchemyCylinderUnitRepository(uow), uow)
                with pytest.raises(CylinderDueForStatutoryTestError):
                    await use_case.execute(
                        ReceiveCylinderUnitCommand(
                            cylinder_unit_id=unit_id,
                            warehouse_id=warehouse_id,
                            performed_by=uuid.uuid4(),
                        )
                    )

        # The block did not partially apply — condition/custody unchanged.
        async for s4 in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(s4, context) as uow:
                still_empty = await SqlAlchemyCylinderUnitRepository(uow).get_by_id(unit_id)
                assert still_empty is not None
                assert still_empty.condition_status == "empty"

    async def test_receives_a_unit_that_is_not_due(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        cylinder_type_id, warehouse_id = await _seed_cylinder_type_and_warehouse(
            admin_engine, tenant_id
        )
        context = RequestTenantContext(tenant_id=tenant_id)
        today = datetime.now(UTC).date()

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repo = SqlAlchemyCylinderUnitRepository(uow)
                registered = await RegisterCylinderUnitUseCase(repo, uow).execute(
                    RegisterCylinderUnitCommand(
                        tenant_id=tenant_id,
                        cylinder_type_id=cylinder_type_id,
                        serial_number="CYL-OK-001",
                        condition_status="empty",
                        custody_type="warehouse",
                        custody_ref_id=warehouse_id,
                    )
                )
                unit_id = registered.id

        async for s2 in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(s2, context) as uow:
                repo = SqlAlchemyCylinderUnitRepository(uow)
                loaded = await repo.get_by_id(unit_id)
                assert loaded is not None
                loaded.record_statutory_test(
                    tested_at=today - timedelta(days=30),
                    due_date=today + timedelta(days=700),  # not due
                    performed_by=uuid.uuid4(),
                )
                await repo.save(loaded)

        async for s3 in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(s3, context) as uow:
                use_case = ReceiveCylinderUnitUseCase(SqlAlchemyCylinderUnitRepository(uow), uow)
                received = await use_case.execute(
                    ReceiveCylinderUnitCommand(
                        cylinder_unit_id=unit_id,
                        warehouse_id=warehouse_id,
                        performed_by=uuid.uuid4(),
                    )
                )
                assert received.condition_status == "filled"

    async def test_a_never_tested_unit_is_not_blocked(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        """Pins the documented policy choice: no `test_due_date` on file
        means "not due," not "blocked until first test." See ADR-042's
        open questions."""
        tenant_id = await _seed_tenant(admin_engine)
        cylinder_type_id, warehouse_id = await _seed_cylinder_type_and_warehouse(
            admin_engine, tenant_id
        )
        context = RequestTenantContext(tenant_id=tenant_id)

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repo = SqlAlchemyCylinderUnitRepository(uow)
                registered = await RegisterCylinderUnitUseCase(repo, uow).execute(
                    RegisterCylinderUnitCommand(
                        tenant_id=tenant_id,
                        cylinder_type_id=cylinder_type_id,
                        serial_number="CYL-NEVER-TESTED-001",
                        condition_status="empty",
                        custody_type="warehouse",
                        custody_ref_id=warehouse_id,
                    )
                )
                unit_id = registered.id

        async for s2 in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(s2, context) as uow:
                use_case = ReceiveCylinderUnitUseCase(SqlAlchemyCylinderUnitRepository(uow), uow)
                received = await use_case.execute(
                    ReceiveCylinderUnitCommand(
                        cylinder_unit_id=unit_id,
                        warehouse_id=warehouse_id,
                        performed_by=uuid.uuid4(),
                    )
                )
                assert received.condition_status == "filled"


class TestSuggestStatutoryTestDueDate:
    async def test_returns_none_when_the_tenant_has_no_interval_configured(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        context = RequestTenantContext(tenant_id=tenant_id)

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                use_case = SuggestStatutoryTestDueDateUseCase(
                    SqlAlchemyTenantConfigurationRepository(uow)
                )
                suggestion = await use_case.execute(
                    SuggestStatutoryTestDueDateQuery(
                        tenant_id=tenant_id, tested_at=datetime.now(UTC).date()
                    )
                )
                assert suggestion is None

    async def test_suggests_tested_at_plus_the_configured_interval(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        context = RequestTenantContext(tenant_id=tenant_id)

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repo = SqlAlchemyTenantConfigurationRepository(uow)
                await repo.add(
                    TenantConfiguration(
                        uuid.uuid4(),
                        tenant_id,
                        "cylinder_statutory_test_interval_months",
                        24,
                        datetime(2020, 1, 1, tzinfo=UTC),
                    )
                )
                await uow.commit()

        tested_at = datetime(2026, 1, 15, tzinfo=UTC).date()
        async for s2 in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(s2, context) as uow:
                use_case = SuggestStatutoryTestDueDateUseCase(
                    SqlAlchemyTenantConfigurationRepository(uow)
                )
                suggestion = await use_case.execute(
                    SuggestStatutoryTestDueDateQuery(tenant_id=tenant_id, tested_at=tested_at)
                )
                assert suggestion == datetime(2028, 1, 15, tzinfo=UTC).date()
