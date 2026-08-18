"""End-to-end smoke test for `api/v1/routers/admin.py`: real HTTP request ->
router -> use case -> repository -> real PostgreSQL/Redis.

`test_auth_endpoints_smoke.py`'s module docstring explains why this class of
test exists: `from __future__ import annotations` + a `TYPE_CHECKING`-only
import anywhere in a `Depends()`-facing function's signature breaks FastAPI's
dependency resolution for the *whole* function, silently — found once
already (ADR-035), and admin.py wires 26 endpoints through ~10 dependency
functions, the largest surface this risk has applied to yet. This test
exercises a representative slice through the real stack, not every endpoint.
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
    """Same shape as `test_auth_endpoints_smoke.py`'s fixture of the same
    name — see that file's module docstring for why `get_settings()` needs
    matching env vars rather than `integration_settings` passed directly.
    """
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable — start it with ./scripts/dev-up.sh")
    if not redis_available:
        pytest.skip("Redis is not reachable — start it with ./scripts/dev-up.sh")

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
        pytest.skip("PostgreSQL is not reachable — start it with ./scripts/dev-up.sh")
    engine = create_async_engine(
        "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:55432/lpg_test"
    )
    try:
        yield engine
    finally:
        await engine.dispose()


async def _seed_staff_user(
    engine: AsyncEngine, *, email: str, password_hash: str, role: str
) -> tuple[uuid.UUID, uuid.UUID]:
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'Admin Smoke Tenant', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"admin-smoke-{uuid.uuid4().hex[:10]}"},
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


async def _login(client: AsyncClient, *, email: str, password: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    access_token: str = response.json()["access_token"]
    return access_token


class TestAdminEndpointsThroughTheRealStack:
    async def test_agency_admin_can_view_tenant_and_manage_branches(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        email = f"{uuid.uuid4().hex}@admin-smoke.example"
        password = "correct horse battery staple 42"
        hasher = Argon2PasswordHasher(integration_settings)
        tenant_id, _user_id = await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="agency_admin",
        )
        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}

        tenant_response = await real_lifespan_client.get("/api/v1/admin/tenant", headers=headers)
        assert tenant_response.status_code == 200, tenant_response.text
        assert tenant_response.json()["id"] == str(tenant_id)

        create_response = await real_lifespan_client.post(
            "/api/v1/admin/branches", json={"name": "Nashik West"}, headers=headers
        )
        assert create_response.status_code == 201, create_response.text
        branch_id = create_response.json()["id"]

        list_response = await real_lifespan_client.get("/api/v1/admin/branches", headers=headers)
        assert list_response.status_code == 200, list_response.text
        assert any(b["id"] == branch_id for b in list_response.json())

        audit_response = await real_lifespan_client.get("/api/v1/admin/audit-log", headers=headers)
        assert audit_response.status_code == 200, audit_response.text
        assert any(
            item["entity_name"] == "branch" and item["entity_id"] == branch_id
            for item in audit_response.json()["items"]
        )

    async def test_a_driver_is_denied_admin_access(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        email = f"{uuid.uuid4().hex}@admin-smoke.example"
        password = "correct horse battery staple 42"
        hasher = Argon2PasswordHasher(integration_settings)
        await _seed_staff_user(
            admin_engine_lpg_test, email=email, password_hash=hasher.hash(password), role="driver"
        )
        token = await _login(real_lifespan_client, email=email, password=password)

        response = await real_lifespan_client.get(
            "/api/v1/admin/tenant", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403

    async def test_an_agency_admin_cannot_manage_platform_feature_flags(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        email = f"{uuid.uuid4().hex}@admin-smoke.example"
        password = "correct horse battery staple 42"
        hasher = Argon2PasswordHasher(integration_settings)
        await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="agency_admin",
        )
        token = await _login(real_lifespan_client, email=email, password=password)

        response = await real_lifespan_client.post(
            "/api/v1/admin/feature-flags",
            json={"key": f"flag-{uuid.uuid4().hex[:8]}", "description": "Test"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403
