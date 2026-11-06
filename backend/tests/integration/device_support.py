"""Fixtures and seed helpers shared by the device-control integration tests
(`test_linked_devices_api.py`, `test_device_enforcement_api.py`). The fixtures
are exposed to the whole integration suite through `conftest.py`."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from lpg.infrastructure.identity.password_hasher import Argon2PasswordHasher
from lpg.infrastructure.persistence.database import Database

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.config.settings import Settings

PASSWORD = "correct horse battery staple 42"


@pytest.fixture
async def devices_client(
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
async def devices_database(
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


class Agency:
    """A seeded tenant with an agency admin and a manager."""

    def __init__(self, tenant_id: uuid.UUID, admin_email: str, manager_email: str) -> None:
        self.tenant_id = tenant_id
        self.admin_email = admin_email
        self.manager_email = manager_email


async def seed_agency(engine: AsyncEngine, hasher: Argon2PasswordHasher) -> Agency:
    suffix = uuid.uuid4().hex[:10]
    admin_email = f"admin-{suffix}@devices.example"
    manager_email = f"manager-{suffix}@devices.example"
    password_hash = hasher.hash(PASSWORD)
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), :name, :slug, 'ops@example.com') RETURNING id"
                ),
                {"name": f"Devices Co {suffix}", "slug": f"devices-{suffix}"},
            )
        ).scalar_one()
        for email, role in ((admin_email, "agency_admin"), (manager_email, "manager")):
            user_id = (
                await conn.execute(
                    text(
                        "INSERT INTO identity.identity_user "
                        "(id, tenant_id, email, password_hash, role) "
                        "VALUES (gen_random_uuid(), :tenant_id, :email, :hash, :role) "
                        "RETURNING id"
                    ),
                    {
                        "tenant_id": str(tenant_id),
                        "email": email,
                        "hash": password_hash,
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
                    "JOIN identity.role r ON r.id = rp.role_id WHERE r.code = :role"
                ),
                {"user_id": user_id, "role": role},
            )
    return Agency(uuid.UUID(str(tenant_id)), admin_email, manager_email)


async def seed_device(
    engine: AsyncEngine,
    tenant_id: uuid.UUID,
    *,
    status: str = "pending",
    app_type: str = "driver_app",
    name: str = "Redmi 12",
) -> uuid.UUID:
    async with engine.begin() as conn:
        license_id = (
            await conn.execute(
                text("SELECT id FROM platform.license WHERE tenant_id = :t"),
                {"t": str(tenant_id)},
            )
        ).scalar_one()
        device_id = (
            await conn.execute(
                text(
                    "INSERT INTO platform.linked_device "
                    "(id, tenant_id, license_id, app_type, device_identifier, display_name, "
                    "status, model, last_user_name, status_changed_at) "
                    "VALUES (gen_random_uuid(), :t, :l, :app, :ident, :name, :status, "
                    "'Redmi 12', 'Ravi', now()) RETURNING id"
                ),
                {
                    "t": str(tenant_id),
                    "l": str(license_id),
                    "app": app_type,
                    "ident": uuid.uuid4().hex + uuid.uuid4().hex,
                    "name": name,
                    "status": status,
                },
            )
        ).scalar_one()
    return uuid.UUID(str(device_id))


async def set_device_cap(engine: AsyncEngine, tenant_id: uuid.UUID, caps: dict[str, Any]) -> None:
    import json

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE platform.license SET device_caps = CAST(:caps AS jsonb) "
                "WHERE tenant_id = :t"
            ),
            {"caps": json.dumps(caps), "t": str(tenant_id)},
        )


async def login_headers(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def devices_hasher(integration_settings: Settings) -> Argon2PasswordHasher:
    return Argon2PasswordHasher(integration_settings)
