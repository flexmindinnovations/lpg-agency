"""Smoke test for the scale registry endpoints through the real ASGI stack
(auth, RBAC, RLS, DB) — Weighment Part 1."""

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
async def client(
    integration_settings: Settings,
    postgres_available: bool,
    redis_available: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[AsyncClient]:
    if not postgres_available or not redis_available:
        pytest.skip("infra not reachable")
    monkeypatch.setenv("LPG_ENVIRONMENT", "local")
    monkeypatch.setenv("LPG_DATABASE_URL", str(integration_settings.database_url))
    monkeypatch.setenv("LPG_REDIS_URL", str(integration_settings.redis_url))

    from lpg.api.app import create_app
    from lpg.config.settings import get_settings

    get_settings.cache_clear()
    app: FastAPI = create_app(integration_settings)
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as http:
            yield http
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


async def _seed_manager_with_warehouse(
    engine: AsyncEngine, *, password_hash: str
) -> tuple[str, uuid.UUID]:
    email = f"{uuid.uuid4().hex}@weighment-smoke.example"
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'Weighment Smoke', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"wt-smoke-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO identity.identity_user "
                "(id, tenant_id, email, password_hash, role) "
                "VALUES (gen_random_uuid(), :tenant_id, :email, :ph, 'manager')"
            ),
            {"tenant_id": str(tenant_id), "email": email, "ph": password_hash},
        )
        user_id = (
            await conn.execute(
                text("SELECT id FROM identity.identity_user WHERE email = :email"), {"email": email}
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO identity.identity_user_permission "
                "(id, user_id, permission_id, created_at) "
                "SELECT gen_random_uuid(), :uid, rp.permission_id, now() "
                "FROM identity.role_permission rp JOIN identity.role r ON r.id = rp.role_id "
                "WHERE r.code = 'manager'"
            ),
            {"uid": str(user_id)},
        )
        branch_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.branch (id, tenant_id, name) "
                    "VALUES (gen_random_uuid(), :tenant_id, 'Smoke Branch') RETURNING id"
                ),
                {"tenant_id": str(tenant_id)},
            )
        ).scalar_one()
        warehouse_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.warehouse (id, tenant_id, branch_id, name, address_line) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, 'Smoke Godown', "
                    "'1 Depot Road') RETURNING id"
                ),
                {"tenant_id": str(tenant_id), "branch_id": str(branch_id)},
            )
        ).scalar_one()
    return email, uuid.UUID(str(warehouse_id))


async def _login(client: AsyncClient, *, email: str, password: str) -> str:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token: str = resp.json()["access_token"]
    return token


async def test_register_list_recalibrate_scale_smoke(
    client: AsyncClient,
    admin_engine_lpg_test: AsyncEngine,
    integration_settings: Settings,
) -> None:
    password = "correct horse battery staple 42"
    hasher = Argon2PasswordHasher(integration_settings)
    email, warehouse_id = await _seed_manager_with_warehouse(
        admin_engine_lpg_test, password_hash=hasher.hash(password)
    )
    token = await _login(client, email=email, password=password)
    headers = {"Authorization": f"Bearer {token}"}

    # MDG cl. 1.2 requires <=10g least count — 11g is rejected as a domain
    # invariant, not just a request-validation error.
    over_spec = await client.post(
        "/api/v1/scales",
        json={
            "warehouse_id": str(warehouse_id),
            "asset_tag": "SCALE-001",
            "least_count_grams": 11,
            "certificate_ref": f"tenant/x/compliance-staging/{uuid.uuid4().hex}_cert.pdf",
            "certificate_expiry_date": "2030-01-01",
        },
        headers=headers,
    )
    assert over_spec.status_code == 422, over_spec.text

    register = await client.post(
        "/api/v1/scales",
        json={
            "warehouse_id": str(warehouse_id),
            "asset_tag": "SCALE-001",
            "least_count_grams": 10,
            "certificate_ref": f"tenant/x/compliance-staging/{uuid.uuid4().hex}_cert.pdf",
            "certificate_expiry_date": "2030-01-01",
            "make": "Avery",
            "model": "AGD-40",
        },
        headers=headers,
    )
    assert register.status_code == 201, register.text
    scale_id = register.json()["id"]
    assert register.json()["status"] == "active"
    assert register.json()["is_expired"] is False

    # Same asset tag at the same warehouse — 409, use recalibrate instead.
    duplicate = await client.post(
        "/api/v1/scales",
        json={
            "warehouse_id": str(warehouse_id),
            "asset_tag": "SCALE-001",
            "least_count_grams": 10,
            "certificate_ref": "tenant/x/compliance-staging/other.pdf",
            "certificate_expiry_date": "2031-01-01",
        },
        headers=headers,
    )
    assert duplicate.status_code == 409, duplicate.text

    listing = await client.get("/api/v1/scales", headers=headers)
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["asset_tag"] == "SCALE-001"

    recalibrate = await client.put(
        f"/api/v1/scales/{scale_id}/certificate",
        json={
            "certificate_ref": f"tenant/x/compliance-staging/{uuid.uuid4().hex}_renewed.pdf",
            "certificate_expiry_date": "2032-06-01",
        },
        headers=headers,
    )
    assert recalibrate.status_code == 200, recalibrate.text
    assert recalibrate.json()["certificate_expiry_date"] == "2032-06-01"

    deactivate = await client.put(
        f"/api/v1/scales/{scale_id}/status", json={"status": "inactive"}, headers=headers
    )
    assert deactivate.status_code == 200, deactivate.text
    assert deactivate.json()["status"] == "inactive"
