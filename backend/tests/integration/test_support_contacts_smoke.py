"""`GET /support/contacts` through the real ASGI stack and PostgreSQL: the
gas-leak helpline defaults to 1906, a tenant can set its own numbers, and
one tenant never sees another's (RLS)."""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from lpg.infrastructure.identity.password_hasher import Argon2PasswordHasher

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration

PASSWORD = "correct horse battery staple 51"


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


async def _seed_tenant_user(engine: AsyncEngine, settings: Settings, config: dict[str, str]) -> str:
    email = f"{uuid.uuid4().hex}@support-contacts.example"
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'Support Contacts Tenant', :slug, "
                    "'ops@example.com') RETURNING id"
                ),
                {"slug": f"support-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO identity.identity_user (id, tenant_id, email, password_hash, role) "
                "VALUES (gen_random_uuid(), :tenant_id, :email, :hash, 'accountant')"
            ),
            {
                "tenant_id": str(tenant_id),
                "email": email,
                "hash": Argon2PasswordHasher(settings).hash(PASSWORD),
            },
        )
        for key, value in config.items():
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant_configuration "
                    "(tenant_id, config_key, config_value, effective_from) "
                    "VALUES (:tenant_id, :key, CAST(:value AS jsonb), now() - interval '1 day')"
                ),
                {"tenant_id": str(tenant_id), "key": key, "value": json.dumps(value)},
            )
    return email


async def _get_contacts(client: AsyncClient, email: str) -> dict[str, object]:
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    response = await client.get(
        "/api/v1/support/contacts",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert response.status_code == 200, response.text
    body: dict[str, object] = response.json()
    return body


class TestSupportContacts:
    async def test_defaults_to_the_national_lpg_helpline(
        self, client: AsyncClient, admin_engine: AsyncEngine, integration_settings: Settings
    ) -> None:
        email = await _seed_tenant_user(admin_engine, integration_settings, {})

        assert await _get_contacts(client, email) == {
            "emergency_helpline": "1906",
            "agency_phone": None,
        }

    async def test_each_tenant_sees_only_its_own_numbers(
        self, client: AsyncClient, admin_engine: AsyncEngine, integration_settings: Settings
    ) -> None:
        configured = await _seed_tenant_user(
            admin_engine,
            integration_settings,
            {"customer_support_phone": "+914012345678", "emergency_helpline_number": "1800-111"},
        )
        other = await _seed_tenant_user(admin_engine, integration_settings, {})

        assert await _get_contacts(client, configured) == {
            "emergency_helpline": "1800-111",
            "agency_phone": "+914012345678",
        }
        assert (await _get_contacts(client, other))["agency_phone"] is None

    async def test_requires_sign_in(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/support/contacts")
        assert response.status_code == 401
