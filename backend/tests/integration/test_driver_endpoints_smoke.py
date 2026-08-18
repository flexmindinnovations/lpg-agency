"""Integration smoke tests for driver and vehicle endpoints.

Tests the full stack through the real FastAPI app, PostgreSQL, and JWT auth.
Mirrors the pattern in test_customer_endpoints_smoke.py.
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
        "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:55432/lpg_test"
    )
    try:
        yield engine
    finally:
        await engine.dispose()


async def _seed_employee(
    engine: AsyncEngine, *, tenant_id: uuid.UUID, branch_id: uuid.UUID
) -> uuid.UUID:
    async with engine.begin() as conn:
        employee_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.employee "
                    "(id, tenant_id, branch_id, employee_code, first_name, last_name, "
                    "phone_number, role, status) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :employee_code, "
                    "'Test', 'Driver', '1234567890', 'driver', 'active') RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id),
                    "employee_code": f"DRV-{uuid.uuid4().hex[:6]}",
                },
            )
        ).scalar_one()
    return uuid.UUID(str(employee_id))


async def _seed_staff_user(
    engine: AsyncEngine, *, email: str, password_hash: str, role: str
) -> tuple[uuid.UUID, uuid.UUID]:
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'Driver Smoke Tenant', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"drv-smoke-{uuid.uuid4().hex[:10]}"},
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
    return uuid.UUID(str(tenant_id)), uuid.UUID(str(user_id))


async def _seed_branch(engine: AsyncEngine, *, tenant_id: uuid.UUID, name: str) -> uuid.UUID:
    async with engine.begin() as conn:
        branch_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.branch (id, tenant_id, name) "
                    "VALUES (gen_random_uuid(), :tenant_id, :name) RETURNING id"
                ),
                {"tenant_id": str(tenant_id), "name": name},
            )
        ).scalar_one()
    return uuid.UUID(str(branch_id))


async def _login(client: AsyncClient, *, email: str, password: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    access_token: str = response.json()["access_token"]
    return access_token


class TestDriverEndpointsThroughRealStack:
    async def test_driver_lifecycle_smoke(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        email = f"{uuid.uuid4().hex}@drv-smoke.example"
        password = "correct horse battery staple 42"
        hasher = Argon2PasswordHasher(integration_settings)
        tenant_id, _user_id = await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="agency_admin",
        )
        branch_id = await _seed_branch(
            admin_engine_lpg_test, tenant_id=tenant_id, name="North Depot"
        )
        employee_id = await _seed_employee(
            admin_engine_lpg_test, tenant_id=tenant_id, branch_id=branch_id
        )

        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Register Driver
        register_response = await real_lifespan_client.post(
            "/api/v1/drivers",
            json={
                "branch_id": str(branch_id),
                "employee_id": str(employee_id),
                "license_number": "DL-12345-MH",
            },
            headers=headers,
        )
        assert register_response.status_code == 201, register_response.text
        driver_id = register_response.json()["id"]
        assert register_response.json()["status"] == "active"

        # 2. Get Driver
        get_response = await real_lifespan_client.get(
            f"/api/v1/drivers/{driver_id}", headers=headers
        )
        assert get_response.status_code == 200, get_response.text
        assert get_response.json()["license_number"] == "DL-12345-MH"

        # 3. Update Driver Status
        patch_response = await real_lifespan_client.patch(
            f"/api/v1/drivers/{driver_id}/status",
            json={"status": "on_leave"},
            headers=headers,
        )
        assert patch_response.status_code == 200, patch_response.text
        assert patch_response.json()["status"] == "on_leave"

        # 4. List Drivers
        list_response = await real_lifespan_client.get("/api/v1/drivers", headers=headers)
        assert list_response.status_code == 200, list_response.text
        assert list_response.json()["total"] >= 1

    async def test_vehicle_lifecycle_smoke(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        email = f"{uuid.uuid4().hex}@veh-smoke.example"
        password = "correct horse battery staple 42"
        hasher = Argon2PasswordHasher(integration_settings)
        tenant_id, _user_id = await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="agency_admin",
        )
        branch_id = await _seed_branch(
            admin_engine_lpg_test, tenant_id=tenant_id, name="Vehicle Depot"
        )
        _employee_id = await _seed_employee(
            admin_engine_lpg_test, tenant_id=tenant_id, branch_id=branch_id
        )

        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Register Vehicle
        reg_number = f"MH12{uuid.uuid4().hex[:4].upper()}"
        register_response = await real_lifespan_client.post(
            "/api/v1/vehicles",
            json={
                "branch_id": str(branch_id),
                "registration_number": reg_number,
                "make": "Tata",
                "model": "Ace",
                "ownership_type": "owned",
                "capacity_units": 20,
            },
            headers=headers,
        )
        assert register_response.status_code == 201, register_response.text
        vehicle_id = register_response.json()["id"]
        assert register_response.json()["capacity_units"] == 20

        # 2. Get Vehicle
        get_response = await real_lifespan_client.get(
            f"/api/v1/vehicles/{vehicle_id}", headers=headers
        )
        assert get_response.status_code == 200, get_response.text
        assert get_response.json()["make"] == "Tata"

        # 3. Update Vehicle Status
        patch_response = await real_lifespan_client.patch(
            f"/api/v1/vehicles/{vehicle_id}/status",
            json={"status": "maintenance"},
            headers=headers,
        )
        assert patch_response.status_code == 200, patch_response.text
        assert patch_response.json()["status"] == "maintenance"

        # 4. List Vehicles
        list_response = await real_lifespan_client.get("/api/v1/vehicles", headers=headers)
        assert list_response.status_code == 200, list_response.text
        assert list_response.json()["total"] >= 1
