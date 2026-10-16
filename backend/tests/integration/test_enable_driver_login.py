"""`SqlAlchemyDriverLoginProvisioner` against real PostgreSQL.

Employees that pre-date the `EmployeeRegistered` handler (seeded or imported)
had no phone login, so Driver App OTP sign-in failed with "No account is
associated with this number". These tests cover giving such an employee a
login and linking it to the driver profile, and every case that must refuse.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from lpg.application.common.errors import ConflictError
from lpg.domain.tenant_admin.employee import Employee
from lpg.infrastructure.identity.driver_login_provisioner import SqlAlchemyDriverLoginProvisioner
from lpg.infrastructure.persistence.database import Database

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


@pytest.fixture
async def admin_engine_lpg_test(postgres_available: bool) -> AsyncIterator[AsyncEngine]:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable — start it with ./scripts/dev-up.sh")
    engine = create_async_engine(
        "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:5433/lpg_test"
    )
    try:
        yield engine
    finally:
        await engine.dispose()


def _phone() -> str:
    return f"+91{uuid.uuid4().int % 10**10:010d}"


async def _seed_tenant(engine: AsyncEngine) -> tuple[uuid.UUID, uuid.UUID]:
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug) "
                    "VALUES (gen_random_uuid(), 'Driver Login Test', :slug) RETURNING id"
                ),
                {"slug": f"driver-login-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
        branch_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.branch (id, tenant_id, name) "
                    "VALUES (gen_random_uuid(), :tenant_id, 'Main') RETURNING id"
                ),
                {"tenant_id": str(tenant_id)},
            )
        ).scalar_one()
    return uuid.UUID(str(tenant_id)), uuid.UUID(str(branch_id))


async def _seed_employee(
    engine: AsyncEngine,
    *,
    tenant_id: uuid.UUID,
    branch_id: uuid.UUID,
    phone_number: str,
    role: str = "driver",
) -> Employee:
    employee_id = uuid.uuid4()
    code = f"EMP-{uuid.uuid4().hex[:6]}"
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO tenant.employee "
                "(id, tenant_id, branch_id, employee_code, first_name, last_name, "
                "phone_number, role, status) "
                "VALUES (:id, :tenant_id, :branch_id, :code, 'Vijay', 'Naidu', "
                ":phone, :role, 'active')"
            ),
            {
                "id": str(employee_id),
                "tenant_id": str(tenant_id),
                "branch_id": str(branch_id),
                "code": code,
                "phone": phone_number,
                "role": role,
            },
        )
    return Employee(
        employee_id=employee_id,
        tenant_id=tenant_id,
        branch_id=branch_id,
        employee_code=code,
        first_name="Vijay",
        last_name="Naidu",
        phone_number=phone_number,
        role=role,
    )


async def _seed_driver_profile(
    engine: AsyncEngine,
    *,
    employee: Employee,
    license_number: str = "TS-DL-2020-0091244",
    identity_user_id: uuid.UUID | None = None,
) -> uuid.UUID:
    async with engine.begin() as conn:
        driver_id = (
            await conn.execute(
                text(
                    "INSERT INTO delivery.driver "
                    "(id, tenant_id, branch_id, employee_id, license_number, status, "
                    "identity_user_id) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :employee_id, "
                    ":license, 'active', :user_id) RETURNING id"
                ),
                {
                    "tenant_id": str(employee.tenant_id),
                    "branch_id": str(employee.branch_id),
                    "employee_id": str(employee.id),
                    "license": license_number,
                    "user_id": str(identity_user_id) if identity_user_id else None,
                },
            )
        ).scalar_one()
    return uuid.UUID(str(driver_id))


async def _seed_login(
    engine: AsyncEngine,
    *,
    tenant_id: uuid.UUID,
    branch_id: uuid.UUID,
    phone_number: str,
    role: str = "driver",
    is_active: bool = True,
) -> uuid.UUID:
    async with engine.begin() as conn:
        user_id = (
            await conn.execute(
                text(
                    "INSERT INTO identity.identity_user "
                    "(id, tenant_id, branch_id, phone_number, role, is_active) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :phone, :role, "
                    ":is_active) RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id),
                    "phone": phone_number,
                    "role": role,
                    "is_active": is_active,
                },
            )
        ).scalar_one()
    return uuid.UUID(str(user_id))


async def _logins(engine: AsyncEngine, tenant_id: uuid.UUID, phone_number: str) -> list[str]:
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT id::text FROM identity.identity_user "
                "WHERE tenant_id = :t AND phone_number = :p"
            ),
            {"t": str(tenant_id), "p": phone_number},
        )
        return [row[0] for row in rows]


async def _driver_rows(
    engine: AsyncEngine, employee_id: uuid.UUID
) -> list[tuple[str, str | None, str, int]]:
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT id::text, identity_user_id::text, license_number, version "
                "FROM delivery.driver WHERE employee_id = :e AND is_deleted = false"
            ),
            {"e": str(employee_id)},
        )
        return [(row[0], row[1], row[2], row[3]) for row in rows]


async def _permission_count(engine: AsyncEngine, user_id: uuid.UUID) -> int:
    async with engine.connect() as conn:
        row = await conn.execute(
            text("SELECT count(*) FROM identity.identity_user_permission WHERE user_id = :u"),
            {"u": str(user_id)},
        )
        return int(row.scalar_one())


class TestEnableDriverLogin:
    async def test_creates_the_login_and_a_pending_driver_profile_for_a_bare_employee(
        self, database: Database, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        tenant_id, branch_id = await _seed_tenant(admin_engine_lpg_test)
        employee = await _seed_employee(
            admin_engine_lpg_test, tenant_id=tenant_id, branch_id=branch_id, phone_number=_phone()
        )

        result = await SqlAlchemyDriverLoginProvisioner(database).enable(tenant_id, employee)

        assert result.login_created is True
        assert result.driver_created is True
        assert await _logins(admin_engine_lpg_test, tenant_id, employee.phone_number) == [
            str(result.user_id)
        ]
        rows = await _driver_rows(admin_engine_lpg_test, employee.id)
        assert [(r[0], r[1], r[2]) for r in rows] == [
            (str(result.driver_id), str(result.user_id), "PENDING")
        ]
        # The driver app's own permissions came with the login.
        assert await _permission_count(admin_engine_lpg_test, result.user_id) > 0

    async def test_links_the_login_to_an_existing_driver_profile_without_touching_it(
        self, database: Database, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        tenant_id, branch_id = await _seed_tenant(admin_engine_lpg_test)
        employee = await _seed_employee(
            admin_engine_lpg_test,
            tenant_id=tenant_id,
            branch_id=branch_id,
            phone_number=_phone(),
        )
        driver_id = await _seed_driver_profile(admin_engine_lpg_test, employee=employee)

        result = await SqlAlchemyDriverLoginProvisioner(database).enable(tenant_id, employee)

        assert result.driver_created is False
        assert result.driver_id == driver_id
        rows = await _driver_rows(admin_engine_lpg_test, employee.id)
        assert [(r[0], r[1], r[2]) for r in rows] == [
            (str(driver_id), str(result.user_id), "TS-DL-2020-0091244")
        ]

    async def test_repeating_the_call_changes_nothing(
        self, database: Database, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        tenant_id, branch_id = await _seed_tenant(admin_engine_lpg_test)
        employee = await _seed_employee(
            admin_engine_lpg_test, tenant_id=tenant_id, branch_id=branch_id, phone_number=_phone()
        )
        provisioner = SqlAlchemyDriverLoginProvisioner(database)
        first = await provisioner.enable(tenant_id, employee)
        before = await _driver_rows(admin_engine_lpg_test, employee.id)

        second = await provisioner.enable(tenant_id, employee)

        assert (second.login_created, second.driver_created) == (False, False)
        assert second.user_id == first.user_id
        assert second.driver_id == first.driver_id
        assert await _driver_rows(admin_engine_lpg_test, employee.id) == before
        assert await _logins(admin_engine_lpg_test, tenant_id, employee.phone_number) == [
            str(first.user_id)
        ]

    async def test_adopts_an_existing_driver_login_that_no_driver_profile_uses(
        self, database: Database, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        tenant_id, branch_id = await _seed_tenant(admin_engine_lpg_test)
        phone = _phone()
        employee = await _seed_employee(
            admin_engine_lpg_test, tenant_id=tenant_id, branch_id=branch_id, phone_number=phone
        )
        existing_login = await _seed_login(
            admin_engine_lpg_test, tenant_id=tenant_id, branch_id=branch_id, phone_number=phone
        )
        await _seed_driver_profile(admin_engine_lpg_test, employee=employee)

        result = await SqlAlchemyDriverLoginProvisioner(database).enable(tenant_id, employee)

        assert result.login_created is False
        assert result.user_id == existing_login
        assert await _logins(admin_engine_lpg_test, tenant_id, phone) == [str(existing_login)]
        rows = await _driver_rows(admin_engine_lpg_test, employee.id)
        assert rows[0][1] == str(existing_login)

    async def test_refuses_when_the_phones_login_already_belongs_to_another_driver(
        self, database: Database, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        """The duplicate-employee case: two employees share a phone and the login
        is linked to the other one's profile."""
        tenant_id, branch_id = await _seed_tenant(admin_engine_lpg_test)
        phone = _phone()
        real = await _seed_employee(
            admin_engine_lpg_test, tenant_id=tenant_id, branch_id=branch_id, phone_number=phone
        )
        duplicate = await _seed_employee(
            admin_engine_lpg_test, tenant_id=tenant_id, branch_id=branch_id, phone_number=phone
        )
        login = await _seed_login(
            admin_engine_lpg_test, tenant_id=tenant_id, branch_id=branch_id, phone_number=phone
        )
        await _seed_driver_profile(
            admin_engine_lpg_test,
            employee=duplicate,
            license_number="PENDING",
            identity_user_id=login,
        )
        await _seed_driver_profile(admin_engine_lpg_test, employee=real)

        with pytest.raises(ConflictError, match="already linked to another driver"):
            await SqlAlchemyDriverLoginProvisioner(database).enable(tenant_id, real)

        assert (await _driver_rows(admin_engine_lpg_test, real.id))[0][1] is None

    async def test_refuses_a_deactivated_login(
        self, database: Database, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        tenant_id, branch_id = await _seed_tenant(admin_engine_lpg_test)
        phone = _phone()
        employee = await _seed_employee(
            admin_engine_lpg_test, tenant_id=tenant_id, branch_id=branch_id, phone_number=phone
        )
        await _seed_login(
            admin_engine_lpg_test,
            tenant_id=tenant_id,
            branch_id=branch_id,
            phone_number=phone,
            is_active=False,
        )

        with pytest.raises(ConflictError, match="deactivated"):
            await SqlAlchemyDriverLoginProvisioner(database).enable(tenant_id, employee)

        assert await _driver_rows(admin_engine_lpg_test, employee.id) == []

    async def test_refuses_when_the_phone_belongs_to_a_non_driver_login(
        self, database: Database, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        tenant_id, branch_id = await _seed_tenant(admin_engine_lpg_test)
        phone = _phone()
        employee = await _seed_employee(
            admin_engine_lpg_test, tenant_id=tenant_id, branch_id=branch_id, phone_number=phone
        )
        await _seed_login(
            admin_engine_lpg_test,
            tenant_id=tenant_id,
            branch_id=branch_id,
            phone_number=phone,
            role="customer",
        )

        with pytest.raises(ConflictError, match="'customer' login"):
            await SqlAlchemyDriverLoginProvisioner(database).enable(tenant_id, employee)

    async def test_another_agencys_login_for_the_same_phone_is_not_considered(
        self, database: Database, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        tenant_id, branch_id = await _seed_tenant(admin_engine_lpg_test)
        other_tenant, other_branch = await _seed_tenant(admin_engine_lpg_test)
        phone = _phone()
        await _seed_login(
            admin_engine_lpg_test,
            tenant_id=other_tenant,
            branch_id=other_branch,
            phone_number=phone,
        )
        employee = await _seed_employee(
            admin_engine_lpg_test, tenant_id=tenant_id, branch_id=branch_id, phone_number=phone
        )

        result = await SqlAlchemyDriverLoginProvisioner(database).enable(tenant_id, employee)

        assert result.login_created is True
        assert await _logins(admin_engine_lpg_test, tenant_id, phone) == [str(result.user_id)]
