"""Smoke tests for the employee router, through the real ASGI stack.

C4 in `planning/MODULE_STATUS.md` found `complaint`, `employee`, `invoice` and
`reporting` shipped with zero test files. This file is `employee`'s share of
R7 (`reporting`'s own share landed as R7a).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from lpg.infrastructure.identity.password_hasher import Argon2PasswordHasher

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration


@pytest.fixture
async def real_lifespan_client(
    integration_settings: Settings,
    postgres_available: bool,
    redis_available: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[AsyncClient]:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable")
    if not redis_available:
        pytest.skip("Redis is not reachable")

    monkeypatch.setenv("LPG_ENVIRONMENT", "local")
    monkeypatch.setenv("LPG_DATABASE_URL", str(integration_settings.database_url))
    monkeypatch.setenv("LPG_REDIS_URL", str(integration_settings.redis_url))

    from lpg.api.app import create_app
    from lpg.config.settings import get_settings

    get_settings.cache_clear()
    app: FastAPI = create_app(integration_settings)
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
            yield http_client
    get_settings.cache_clear()


@pytest.fixture
async def admin_engine_lpg_test(postgres_available: bool) -> AsyncIterator[AsyncEngine]:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable")
    engine = create_async_engine(
        "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:5433/lpg_test"
    )
    try:
        yield engine
    finally:
        await engine.dispose()


async def _seed_staff_user(
    engine: AsyncEngine, *, email: str, password_hash: str, role: str, tenant_name: str
) -> uuid.UUID:
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), :name, :slug, 'ops@example.com') RETURNING id"
                ),
                {"name": tenant_name, "slug": f"employee-smoke-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
        user_id = (
            await conn.execute(
                text(
                    "INSERT INTO identity.identity_user "
                    "(id, tenant_id, email, password_hash, role) "
                    "VALUES (gen_random_uuid(), :tenant_id, :email, :password_hash, :role) "
                    "RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "email": email,
                    "password_hash": password_hash,
                    "role": role,
                },
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO identity.identity_user_permission "
                "(id, user_id, permission_id, created_at) "
                "SELECT gen_random_uuid(), :user_id, rp.permission_id, now() "
                "FROM identity.role_permission rp "
                "JOIN identity.role r ON r.id = rp.role_id "
                "WHERE r.code = :role"
            ),
            {"user_id": user_id, "role": role},
        )
    return uuid.UUID(str(tenant_id))


async def _login(client: AsyncClient, *, email: str, password: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    access_token: str = response.json()["access_token"]
    return access_token


class TestEmployeeEndpointsThroughTheRealStack:
    async def test_register_and_list_full_lifecycle(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        hasher = Argon2PasswordHasher(integration_settings)
        email = f"{uuid.uuid4().hex}@employee-smoke.example"
        password = "correct horse battery staple 42"
        await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="agency_admin",
            tenant_name="Employee Smoke Tenant (lifecycle)",
        )
        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}
        client = real_lifespan_client

        register_response = await client.post(
            "/api/v1/employees",
            headers=headers,
            json={
                "branch_id": str(uuid.uuid4()),
                "first_name": "Asha",
                "last_name": "Verma",
                "phone_number": "+919876543210",
                "role": "driver",
                "email": "asha@example.com",
            },
        )
        assert register_response.status_code == 201, register_response.text
        body = register_response.json()
        assert body["first_name"] == "Asha"
        assert body["status"] == "active"
        assert body["employee_code"]

        list_response = await client.get("/api/v1/employees", headers=headers)
        assert list_response.status_code == 200, list_response.text
        list_body = list_response.json()
        assert list_body["total"] == 1
        assert list_body["items"][0]["id"] == body["id"]

    async def test_list_is_tenant_scoped(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        hasher = Argon2PasswordHasher(integration_settings)
        password = "correct horse battery staple 42"

        email = f"{uuid.uuid4().hex}@employee-smoke.example"
        await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="agency_admin",
            tenant_name="Employee Smoke Tenant (own)",
        )
        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}

        register_response = await real_lifespan_client.post(
            "/api/v1/employees",
            headers=headers,
            json={
                "branch_id": str(uuid.uuid4()),
                "first_name": "Own",
                "last_name": "Tenant",
                "phone_number": "+919876500001",
                "role": "driver",
            },
        )
        assert register_response.status_code == 201, register_response.text

        other_email = f"{uuid.uuid4().hex}@employee-smoke.example"
        await _seed_staff_user(
            admin_engine_lpg_test,
            email=other_email,
            password_hash=hasher.hash(password),
            role="agency_admin",
            tenant_name="Employee Smoke Tenant (other)",
        )
        other_token = await _login(real_lifespan_client, email=other_email, password=password)
        other_headers = {"Authorization": f"Bearer {other_token}"}
        other_register_response = await real_lifespan_client.post(
            "/api/v1/employees",
            headers=other_headers,
            json={
                "branch_id": str(uuid.uuid4()),
                "first_name": "Other",
                "last_name": "Tenant",
                "phone_number": "+919876500002",
                "role": "driver",
            },
        )
        assert other_register_response.status_code == 201, other_register_response.text

        list_response = await real_lifespan_client.get("/api/v1/employees", headers=headers)
        assert list_response.status_code == 200, list_response.text
        body = list_response.json()
        assert body["total"] == 1
        assert body["items"][0]["first_name"] == "Own"

    async def test_registering_a_driver_provisions_login_and_a_driver_record(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        """Regression: `SqlAlchemyEmployeeRepository.save()`'s insert branch
        built the ORM row straight from the passed-in `Employee` without ever
        calling `register_aggregate` on it — the one call that makes the
        UnitOfWork's `collect_events()` see an aggregate at all. The newly
        constructed employee's pending `EmployeeRegistered` was silently
        never collected, so `register_tenant_admin_handlers`'s
        `IdentityUser`/`Driver` provisioning never ran for *any* employee
        ever registered through this endpoint — no exception, no log line,
        `commit()` just found nothing to dispatch. A driver "registered"
        this way could never actually sign in: `POST /auth/otp/verify`
        answers "No account is associated with this number." forever,
        discovered live against production (2026-09-30) trying to get a
        fresh test driver logged into the driver app.
        """
        hasher = Argon2PasswordHasher(integration_settings)
        email = f"{uuid.uuid4().hex}@employee-smoke.example"
        password = "correct horse battery staple 42"
        tenant_id = await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="agency_admin",
            tenant_name="Employee Smoke Tenant (driver provisioning)",
        )
        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}
        phone_number = "+919876511111"

        register_response = await real_lifespan_client.post(
            "/api/v1/employees",
            headers=headers,
            json={
                "branch_id": str(uuid.uuid4()),
                "first_name": "New",
                "last_name": "Driver",
                "phone_number": phone_number,
                "role": "driver",
            },
        )
        assert register_response.status_code == 201, register_response.text

        async with admin_engine_lpg_test.connect() as conn:
            identity_row = (
                await conn.execute(
                    text(
                        "SELECT role, is_active FROM identity.identity_user "
                        "WHERE tenant_id = :tenant_id AND phone_number = :phone"
                    ),
                    {"tenant_id": str(tenant_id), "phone": phone_number},
                )
            ).first()
            driver_row = (
                await conn.execute(
                    text("SELECT license_number FROM delivery.driver WHERE tenant_id = :tenant_id"),
                    {"tenant_id": str(tenant_id)},
                )
            ).first()

        assert identity_row is not None, (
            "no identity_user for this phone — the employee can never log in"
        )
        assert identity_row.role == "driver"
        assert identity_row.is_active is True
        assert driver_row is not None
        assert driver_row.license_number == "PENDING"

        # `POST /auth/otp/request` (which existed before this fix) claims
        # success either way (it never reveals whether a phone is known) —
        # a real client can only tell the difference by trying to verify.
        # This is what actually broke: 404-shaped "No account is associated
        # with this number" for a driver the admin just registered.
        otp_request_response = await real_lifespan_client.post(
            "/api/v1/auth/otp/request",
            json={"tenant_id": str(tenant_id), "phone_number": phone_number},
        )
        assert otp_request_response.status_code == 204, otp_request_response.text

    async def test_register_employee_denied_without_users_manage(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        """`manager` has `users:read` but not `users:manage`."""
        hasher = Argon2PasswordHasher(integration_settings)
        email = f"{uuid.uuid4().hex}@employee-smoke.example"
        password = "correct horse battery staple 42"
        await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="manager",
            tenant_name="Employee Smoke Tenant (denied register)",
        )
        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}

        response = await real_lifespan_client.post(
            "/api/v1/employees",
            headers=headers,
            json={
                "branch_id": str(uuid.uuid4()),
                "first_name": "N",
                "last_name": "A",
                "phone_number": "+919999999999",
                "role": "driver",
            },
        )
        assert response.status_code == 403, response.text

    async def test_list_employees_denied_without_users_read(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        hasher = Argon2PasswordHasher(integration_settings)
        email = f"{uuid.uuid4().hex}@employee-smoke.example"
        password = "correct horse battery staple 42"
        await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="driver",
            tenant_name="Employee Smoke Tenant (denied list)",
        )
        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}

        response = await real_lifespan_client.get("/api/v1/employees", headers=headers)
        assert response.status_code == 403, response.text
