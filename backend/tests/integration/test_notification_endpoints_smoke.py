"""Smoke tests for Notification endpoints."""

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
                "INSERT INTO identity.identity_user_permission (id, user_id, permission_id, created_at) "
                "SELECT gen_random_uuid(), :user_id, rp.permission_id, now() "
                "FROM identity.role_permission rp "
                "JOIN identity.role r ON r.id = rp.role_id "
                "WHERE r.code = :role"
            ),
            {"user_id": user_id, "role": role},
        )
    return uuid.UUID(str(tenant_id)), uuid.UUID(str(user_id))


async def _seed_notification(
    engine: AsyncEngine, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> uuid.UUID:
    async with engine.begin() as conn:
        notif_id = (
            await conn.execute(
                text(
                    "INSERT INTO notification.in_app_notification "
                    "(id, tenant_id, recipient_user_id, notification_type, title, body, "
                    "reference_type, reference_id, is_read, created_at) "
                    "VALUES (gen_random_uuid(), :tenant_id, :user_id, 'booking_confirmed', "
                    "'Test Title', 'Test Body', 'order', gen_random_uuid(), false, now()) "
                    "RETURNING id"
                ),
                {"tenant_id": str(tenant_id), "user_id": str(user_id)},
            )
        ).scalar_one()
    return uuid.UUID(str(notif_id))


async def _login(client: AsyncClient, *, email: str, password: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    access_token: str = response.json()["access_token"]
    return access_token


class TestNotificationEndpointsThroughTheRealStack:
    async def test_notification_endpoints(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        email = f"{uuid.uuid4().hex}@admin-smoke.example"
        password = "correct horse battery staple 42"
        hasher = Argon2PasswordHasher(integration_settings)
        tenant_id, user_id = await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="agency_admin",
        )
        notification_id = await _seed_notification(admin_engine_lpg_test, tenant_id, user_id)
        
        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Unread count should be 1
        count_resp = await real_lifespan_client.get("/api/v1/notifications/unread-count", headers=headers)
        if count_resp.status_code != 200:
            print("ERROR", count_resp.json())
        assert count_resp.status_code == 200
        assert count_resp.json()["count"] == 1
        
        # 2. List notifications should contain it
        list_resp = await real_lifespan_client.get("/api/v1/notifications", headers=headers)
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == str(notification_id)
        assert items[0]["is_read"] is False
        
        # 3. Mark read
        mark_read_resp = await real_lifespan_client.patch(f"/api/v1/notifications/{notification_id}/read", headers=headers)
        assert mark_read_resp.status_code == 200
        
        # 4. Check unread count is 0
        count_resp = await real_lifespan_client.get("/api/v1/notifications/unread-count", headers=headers)
        assert count_resp.json()["count"] == 0
        
        # 5. Mark all read
        mark_all_read_resp = await real_lifespan_client.post("/api/v1/notifications/read-all", headers=headers)
        assert mark_all_read_resp.status_code == 204
