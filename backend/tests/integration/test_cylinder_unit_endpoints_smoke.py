"""Smoke test for the cylinder unit endpoints through the real ASGI stack
(auth, RBAC via `cylinder_units:manage`/`cylinder_units:read`, RLS, DB) —
Cylinder Identity, Phase 20 subsystem 3."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
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
) -> tuple[str, uuid.UUID, uuid.UUID]:
    email = f"{uuid.uuid4().hex}@cylinder-unit-smoke.example"
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'Cylinder Unit Smoke', :slug, "
                    "'ops@example.com') RETURNING id"
                ),
                {"slug": f"cyl-smoke-{uuid.uuid4().hex[:10]}"},
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
                    "INSERT INTO tenant.warehouse (id, tenant_id, branch_id, name, "
                    "address_line) VALUES (gen_random_uuid(), :tenant_id, :branch_id, "
                    "'Smoke Godown', '1 Depot Road') RETURNING id"
                ),
                {"tenant_id": str(tenant_id), "branch_id": str(branch_id)},
            )
        ).scalar_one()
        cylinder_type_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.cylinder_type (id, tenant_id, name, weight_kg) "
                    "VALUES (gen_random_uuid(), :tenant_id, '14.2kg Domestic', 14.2) "
                    "RETURNING id"
                ),
                {"tenant_id": str(tenant_id)},
            )
        ).scalar_one()
    return email, uuid.UUID(str(warehouse_id)), uuid.UUID(str(cylinder_type_id))


async def _seed_driver(engine: AsyncEngine, *, password_hash: str) -> str:
    email = f"{uuid.uuid4().hex}@cylinder-unit-smoke-driver.example"
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'Cylinder Unit Smoke Driver', :slug, "
                    "'ops@example.com') RETURNING id"
                ),
                {"slug": f"cyl-smoke-drv-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO identity.identity_user "
                "(id, tenant_id, email, password_hash, role) "
                "VALUES (gen_random_uuid(), :tenant_id, :email, :ph, 'driver')"
            ),
            {"tenant_id": str(tenant_id), "email": email, "ph": password_hash},
        )
    return email


async def _login(client: AsyncClient, *, email: str, password: str) -> str:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token: str = resp.json()["access_token"]
    return token


async def test_register_list_lifecycle_smoke(
    client: AsyncClient,
    admin_engine_lpg_test: AsyncEngine,
    integration_settings: Settings,
) -> None:
    password = "correct horse battery staple 42"
    hasher = Argon2PasswordHasher(integration_settings)
    email, warehouse_id, cylinder_type_id = await _seed_manager_with_warehouse(
        admin_engine_lpg_test, password_hash=hasher.hash(password)
    )
    token = await _login(client, email=email, password=password)
    headers = {"Authorization": f"Bearer {token}"}

    register = await client.post(
        "/api/v1/cylinder-units",
        json={
            "cylinder_type_id": str(cylinder_type_id),
            "serial_number": f"CYL-SMOKE-{uuid.uuid4().hex[:8]}",
            "condition_status": "empty",
            "custody_type": "warehouse",
            "custody_ref_id": str(warehouse_id),
        },
        headers=headers,
    )
    assert register.status_code == 201, register.text
    body = register.json()
    unit_id = body["id"]
    serial = body["serial_number"]
    assert body["condition_status"] == "empty"
    assert body["is_retired"] is False
    assert body["is_due_for_test"] is False  # never tested -> not due

    # Same serial again — 409, use a different serial.
    duplicate = await client.post(
        "/api/v1/cylinder-units",
        json={
            "cylinder_type_id": str(cylinder_type_id),
            "serial_number": serial,
            "condition_status": "empty",
            "custody_type": "warehouse",
            "custody_ref_id": str(warehouse_id),
        },
        headers=headers,
    )
    assert duplicate.status_code == 409, duplicate.text

    listing = await client.get("/api/v1/cylinder-units", headers=headers)
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 1

    get_one = await client.get(f"/api/v1/cylinder-units/{unit_id}", headers=headers)
    assert get_one.status_code == 200, get_one.text
    assert get_one.json()["serial_number"] == serial
    assert get_one.json()["qr_code"] == f"CYL-{serial}"

    # Quick lookup by serial and by QR code
    lookup_serial = await client.get(
        "/api/v1/cylinder-units/lookup", params={"code": serial}, headers=headers
    )
    assert lookup_serial.status_code == 200, lookup_serial.text
    assert lookup_serial.json()["id"] == unit_id

    lookup_qr = await client.get(
        "/api/v1/cylinder-units/lookup", params={"code": f"CYL-{serial}"}, headers=headers
    )
    assert lookup_qr.status_code == 200, lookup_qr.text
    assert lookup_qr.json()["id"] == unit_id

    lookup_missing = await client.get(
        "/api/v1/cylinder-units/lookup", params={"code": "NON-EXISTENT-CODE"}, headers=headers
    )
    assert lookup_missing.status_code == 404

    # Print label PDF
    label_resp = await client.post(f"/api/v1/cylinder-units/{unit_id}/label", headers=headers)
    assert label_resp.status_code == 200, label_resp.text
    assert label_resp.headers["content-type"] == "application/pdf"
    assert label_resp.content[:5] == b"%PDF-"

    # Move custody back to warehouse before the rest of lifecycle
    batch_resp = await client.post(
        "/api/v1/cylinder-units/batch-custody",
        json={
            "cylinder_unit_ids": [unit_id],
            "custody_type": "warehouse",
            "custody_ref_id": str(warehouse_id),
        },
        headers=headers,
    )
    assert batch_resp.status_code == 200, batch_resp.text
    assert batch_resp.json()["updated_count"] == 1

    # No cylinder_statutory_test_interval_months configured for this tenant
    # -> no guessed suggestion.
    suggest = await client.get(
        "/api/v1/cylinder-units/suggest-test-due-date",
        params={"tested_at": "2026-01-15"},
        headers=headers,
    )
    assert suggest.status_code == 200, suggest.text
    assert suggest.json()["suggested_due_date"] is None

    # Record an overdue test, then confirm receive() is blocked (Rule 26).
    overdue_due_date = (datetime.now(UTC).date() - timedelta(days=5)).isoformat()
    record_test = await client.post(
        f"/api/v1/cylinder-units/{unit_id}/test",
        json={"tested_at": "2024-01-01", "due_date": overdue_due_date},
        headers=headers,
    )
    assert record_test.status_code == 200, record_test.text
    assert record_test.json()["is_due_for_test"] is True

    blocked_receive = await client.post(
        f"/api/v1/cylinder-units/{unit_id}/receive",
        json={"warehouse_id": str(warehouse_id)},
        headers=headers,
    )
    assert blocked_receive.status_code == 409, blocked_receive.text
    # Same manual catch-and-rewrap-to-HTTPException pattern the existing
    # scale/weighment endpoints in this router already use — it loses the
    # specific `CylinderDueForStatutoryTestError.error_code` in favour of
    # the generic 409 fallback (`code_by_status` has no 409 entry), so this
    # asserts the message content instead, not the (generic) error_code.
    assert "due for statutory retest" in blocked_receive.json()["detail"]

    # Record a fresh, not-due test, then receive succeeds.
    future_due_date = (datetime.now(UTC).date() + timedelta(days=700)).isoformat()
    record_test_2 = await client.post(
        f"/api/v1/cylinder-units/{unit_id}/test",
        json={"tested_at": "2026-01-01", "due_date": future_due_date},
        headers=headers,
    )
    assert record_test_2.status_code == 200, record_test_2.text
    assert record_test_2.json()["is_due_for_test"] is False

    receive = await client.post(
        f"/api/v1/cylinder-units/{unit_id}/receive",
        json={"warehouse_id": str(warehouse_id)},
        headers=headers,
    )
    assert receive.status_code == 200, receive.text
    assert receive.json()["condition_status"] == "filled"
    assert receive.json()["custody_type"] == "warehouse"

    # filled -> empty is a valid condition move for a single unit.
    change_condition = await client.post(
        f"/api/v1/cylinder-units/{unit_id}/condition",
        json={"new_status": "empty", "reason": "delivered and returned by a test customer"},
        headers=headers,
    )
    assert change_condition.status_code == 200, change_condition.text
    assert change_condition.json()["condition_status"] == "empty"

    # empty -> filled directly via /condition is not a real transition —
    # only receive() charges a cylinder (Rule 26 must be checked first).
    invalid_condition = await client.post(
        f"/api/v1/cylinder-units/{unit_id}/condition",
        json={"new_status": "filled"},
        headers=headers,
    )
    assert invalid_condition.status_code == 422, invalid_condition.text

    move_custody = await client.post(
        f"/api/v1/cylinder-units/{unit_id}/custody",
        json={"custody_type": "vehicle", "custody_ref_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert move_custody.status_code == 200, move_custody.text
    assert move_custody.json()["custody_type"] == "vehicle"

    retire = await client.post(f"/api/v1/cylinder-units/{unit_id}/retire", headers=headers)
    assert retire.status_code == 200, retire.text
    assert retire.json()["is_retired"] is True

    # A retired unit no longer appears in the (non-retired-only) listing.
    listing_after_retire = await client.get("/api/v1/cylinder-units", headers=headers)
    assert listing_after_retire.status_code == 200, listing_after_retire.text
    assert listing_after_retire.json()["total"] == 0

    # But it's still individually reachable — Rule 27's lifetime-record
    # requirement.
    still_reachable = await client.get(f"/api/v1/cylinder-units/{unit_id}", headers=headers)
    assert still_reachable.status_code == 200, still_reachable.text
    assert still_reachable.json()["is_retired"] is True


async def test_cylinder_units_permission_is_enforced(
    client: AsyncClient,
    admin_engine_lpg_test: AsyncEngine,
    integration_settings: Settings,
) -> None:
    """A role with no `cylinder_units:*` grant (driver) gets a 403, not a
    silent empty result."""
    password = "correct horse battery staple 42"
    hasher = Argon2PasswordHasher(integration_settings)
    email = await _seed_driver(admin_engine_lpg_test, password_hash=hasher.hash(password))
    token = await _login(client, email=email, password=password)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/api/v1/cylinder-units", headers=headers)
    assert resp.status_code == 403, resp.text
