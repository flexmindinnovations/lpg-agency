"""Per-agency notification settings (ADR-068) through the real ASGI stack and
PostgreSQL: saved per event, validated, reset, row-level isolated, and applied
by the notification resolver."""

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

PASSWORD = "correct horse battery staple 42"


@pytest.fixture
async def client(
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
async def admin(postgres_available: bool) -> AsyncIterator[AsyncEngine]:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable")
    engine = create_async_engine(
        "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:5433/lpg_test"
    )
    try:
        yield engine
    finally:
        await engine.dispose()


async def _seed_agency_admin(engine: AsyncEngine, settings: Settings) -> tuple[uuid.UUID, str]:
    email = f"{uuid.uuid4().hex}@notif-settings.example"
    role = "agency_admin"
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'Gateway Tenant', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"notif-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
        user_id = (
            await conn.execute(
                text(
                    "INSERT INTO identity.identity_user "
                    "(id, tenant_id, email, password_hash, role) "
                    "VALUES (gen_random_uuid(), :tenant_id, :email, :hash, :role) RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "email": email,
                    "hash": Argon2PasswordHasher(settings).hash(PASSWORD),
                    "role": role,
                },
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO identity.identity_user_permission "
                "(id, user_id, permission_id, created_at) "
                "SELECT gen_random_uuid(), :user_id, rp.permission_id, now() "
                "FROM identity.role_permission rp JOIN identity.role r ON r.id = rp.role_id "
                "WHERE r.code = :role"
            ),
            {"user_id": user_id, "role": role},
        )
    return uuid.UUID(str(tenant_id)), email


async def _headers(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _by_type(payload: dict) -> dict:
    return {e["notification_type"]: e for e in payload["events"]}


@pytest.mark.asyncio
class TestNotificationSettings:
    async def test_defaults_save_validate_reset(
        self, client: AsyncClient, admin: AsyncEngine, integration_settings: Settings
    ) -> None:
        _, email = await _seed_agency_admin(admin, integration_settings)
        headers = await _headers(client, email)

        listed = await client.get("/api/v1/notification-settings", headers=headers)
        assert listed.status_code == 200, listed.text
        events = _by_type(listed.json())
        assert events["order_placed_staff"]["push"]["enabled"] is True
        assert events["order_placed_staff"]["customized"] is False
        assert events["order_placed_staff"]["sms"]["available"] is False

        url = "/api/v1/notification-settings/order_placed_staff"
        off = {"in_app": True, "push": False, "sms": False, "email": False}
        saved = await client.put(url, headers=headers, json=off)
        assert saved.status_code == 200, saved.text
        assert saved.json()["push"]["enabled"] is False
        assert saved.json()["customized"] is True
        again = _by_type(
            (await client.get("/api/v1/notification-settings", headers=headers)).json()
        )
        assert again["order_placed_staff"]["push"]["enabled"] is False

        # Critical events keep their in-app alert; unavailable channels are refused.
        critical = await client.put(
            "/api/v1/notification-settings/cancellation_requested_staff",
            headers=headers,
            json={**off, "in_app": False},
        )
        assert critical.status_code == 422
        no_sms = await client.put(url, headers=headers, json={**off, "sms": True})
        assert no_sms.status_code == 422
        unknown = await client.put("/api/v1/notification-settings/nope", headers=headers, json=off)
        assert unknown.status_code == 422

        reset = await client.delete(url, headers=headers)
        assert reset.status_code == 200
        assert reset.json()["customized"] is False
        assert reset.json()["push"]["enabled"] is True

    async def test_agencies_do_not_share_settings(
        self, client: AsyncClient, admin: AsyncEngine, integration_settings: Settings
    ) -> None:
        _, first_email = await _seed_agency_admin(admin, integration_settings)
        _, second_email = await _seed_agency_admin(admin, integration_settings)
        first = await _headers(client, first_email)
        second = await _headers(client, second_email)
        await client.put(
            "/api/v1/notification-settings/order_placed_staff",
            headers=first,
            json={"in_app": False, "push": False, "sms": False, "email": False},
        )
        other = _by_type((await client.get("/api/v1/notification-settings", headers=second)).json())
        assert other["order_placed_staff"]["customized"] is False
        assert other["order_placed_staff"]["in_app"]["enabled"] is True

    async def test_the_resolver_applies_the_override(
        self, client: AsyncClient, admin: AsyncEngine, integration_settings: Settings
    ) -> None:
        from lpg.api.app import get_app_state
        from lpg.application.common.tenant import RequestTenantContext
        from lpg.infrastructure.notification.recipients import NotificationResolver
        from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

        tenant_id, email = await _seed_agency_admin(admin, integration_settings)
        headers = await _headers(client, email)
        await client.put(
            "/api/v1/notification-settings/order_placed_staff",
            headers=headers,
            json={"in_app": True, "push": False, "sms": False, "email": False},
        )
        database = get_app_state().database
        assert database is not None
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(
                session, RequestTenantContext(tenant_id=tenant_id)
            ) as uow:
                from lpg.infrastructure.notification.catalog import SPECS

                resolver = NotificationResolver(uow, tenant_id)
                spec = SPECS["order_placed_staff"]
                changed = await resolver._channels("order_placed_staff", spec, spec.push)
                untouched = await resolver._channels(
                    "complaint_raised_staff", SPECS["complaint_raised_staff"], True
                )
        assert changed.push is False and changed.in_app is True
        assert untouched.push is True
