"""Smoke test for the driver/vehicle compliance-document endpoints through the
real ASGI stack (auth, RBAC, RLS, DB)."""

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
        "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:5433/lpg_test"
    )
    try:
        yield engine
    finally:
        await engine.dispose()


async def _seed_manager(engine: AsyncEngine, *, password_hash: str) -> tuple[uuid.UUID, str]:
    email = f"{uuid.uuid4().hex}@compliance-smoke.example"
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'Compliance Smoke', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"cmp-smoke-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
        user_id = (
            await conn.execute(
                text(
                    "INSERT INTO identity.identity_user "
                    "(id, tenant_id, email, password_hash, role) "
                    "VALUES (gen_random_uuid(), :tenant_id, :email, :ph, 'manager') RETURNING id"
                ),
                {"tenant_id": str(tenant_id), "email": email, "ph": password_hash},
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
    return uuid.UUID(str(tenant_id)), email


async def _login(client: AsyncClient, *, email: str, password: str) -> str:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token: str = resp.json()["access_token"]
    return token


async def test_driver_document_add_list_verify_smoke(
    client: AsyncClient,
    admin_engine_lpg_test: AsyncEngine,
    integration_settings: Settings,
) -> None:
    password = "correct horse battery staple 42"
    hasher = Argon2PasswordHasher(integration_settings)
    _tenant_id, email = await _seed_manager(
        admin_engine_lpg_test, password_hash=hasher.hash(password)
    )
    token = await _login(client, email=email, password=password)
    headers = {"Authorization": f"Bearer {token}"}
    driver_id = str(uuid.uuid4())

    add = await client.post(
        f"/api/v1/drivers/{driver_id}/documents",
        json={
            "doc_type": "driving_licence",
            "document_number": "MH1220110012345",
            "file_ref": f"tenant/x/compliance-staging/{uuid.uuid4().hex}_dl.png",
            "expiry_date": "2030-01-01",
        },
        headers=headers,
    )
    assert add.status_code == 201, add.text
    doc_id = add.json()["id"]
    assert add.json()["verification_status"] == "pending"

    # A second document of the same type is a 409 (use replace).
    dup = await client.post(
        f"/api/v1/drivers/{driver_id}/documents",
        json={
            "doc_type": "driving_licence",
            "document_number": "MH1220110099999",
            "file_ref": "tenant/x/compliance-staging/other.png",
            "expiry_date": "2031-01-01",
        },
        headers=headers,
    )
    assert dup.status_code == 409, dup.text

    listing = await client.get(f"/api/v1/drivers/{driver_id}/documents", headers=headers)
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["file_url"]  # presigned URL resolved

    verify = await client.post(
        f"/api/v1/compliance-documents/{doc_id}/verify",
        json={"status": "verified"},
        headers=headers,
    )
    assert verify.status_code == 200, verify.text
    assert verify.json()["verification_status"] == "verified"

    tenant_list = await client.get(
        "/api/v1/compliance-documents?owner_type=driver&status=verified", headers=headers
    )
    assert tenant_list.status_code == 200, tenant_list.text
    assert tenant_list.json()["total"] >= 1


async def test_warehouse_and_tenant_document_add_list_smoke(
    client: AsyncClient,
    admin_engine_lpg_test: AsyncEngine,
    integration_settings: Settings,
) -> None:
    """Compliance Calendar (ADR-044) — the new warehouse/tenant wrapper
    endpoints, reusing the same generic use cases as driver/vehicle."""
    password = "correct horse battery staple 42"
    hasher = Argon2PasswordHasher(integration_settings)
    _tenant_id, email = await _seed_manager(
        admin_engine_lpg_test, password_hash=hasher.hash(password)
    )
    token = await _login(client, email=email, password=password)
    headers = {"Authorization": f"Bearer {token}"}
    warehouse_id = str(uuid.uuid4())

    add_warehouse = await client.post(
        f"/api/v1/warehouses/{warehouse_id}/documents",
        json={
            "doc_type": "peso_form_f",
            "document_number": "PESO/FORM-F/2026/0042",
            "file_ref": f"tenant/x/compliance-staging/{uuid.uuid4().hex}_peso.png",
            "expiry_date": "2029-01-01",
        },
        headers=headers,
    )
    assert add_warehouse.status_code == 201, add_warehouse.text
    assert add_warehouse.json()["owner_type"] == "warehouse"

    list_warehouse = await client.get(
        f"/api/v1/warehouses/{warehouse_id}/documents", headers=headers
    )
    assert list_warehouse.status_code == 200, list_warehouse.text
    assert list_warehouse.json()["total"] == 1

    add_tenant = await client.post(
        "/api/v1/tenant/documents",
        json={
            "doc_type": "insurance_policy",
            "document_number": "INS-2026-998877",
            "file_ref": f"tenant/x/compliance-staging/{uuid.uuid4().hex}_ins.png",
            "expiry_date": "2027-06-01",
        },
        headers=headers,
    )
    assert add_tenant.status_code == 201, add_tenant.text
    assert add_tenant.json()["owner_type"] == "tenant"
    assert add_tenant.json()["owner_id"] == str(_tenant_id)

    list_tenant = await client.get("/api/v1/tenant/documents", headers=headers)
    assert list_tenant.status_code == 200, list_tenant.text
    assert list_tenant.json()["total"] == 1

    # A doc_type that belongs to a different owner is rejected (422 domain error).
    wrong_type = await client.post(
        f"/api/v1/warehouses/{warehouse_id}/documents",
        json={
            "doc_type": "insurance_policy",
            "document_number": "X",
            "file_ref": "tenant/x/compliance-staging/wrong.png",
            "expiry_date": "2028-01-01",
        },
        headers=headers,
    )
    assert wrong_type.status_code == 422, wrong_type.text
