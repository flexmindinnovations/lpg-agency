"""Smoke test for the TDT rating endpoints through the real ASGI stack
(auth, RBAC via the new `tdt:read` permission, RLS, DB) — Phase 20
subsystem 2."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
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


async def _seed_manager_tenant_customer_and_order(
    engine: AsyncEngine, *, password_hash: str
) -> tuple[str, uuid.UUID]:
    """Seeds a manager user (with `tdt:read` via the `manager` role grant
    from `c7f4a2e9b6d1`), a customer, and one order delivered same-day
    within the current calendar quarter — enough for the live-projection
    endpoint to return `total_orders == 1` without depending on wall-clock
    timing beyond "today"."""
    email = f"{uuid.uuid4().hex}@tdt-smoke.example"
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'TDT Smoke', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"tdt-smoke-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
        branch_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.branch (id, tenant_id, name) "
                    "VALUES (gen_random_uuid(), :tenant_id, 'Smoke Branch') RETURNING id"
                ),
                {"tenant_id": str(tenant_id)},
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

        identity_customer_id = (
            await conn.execute(
                text(
                    "INSERT INTO identity.identity_user "
                    "(id, tenant_id, branch_id, email, password_hash, role) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :email, 'x', "
                    "'customer') RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id),
                    "email": f"cust-{uuid.uuid4().hex[:10]}@tdt-smoke.example",
                },
            )
        ).scalar_one()
        customer_id = (
            await conn.execute(
                text(
                    "INSERT INTO customer.customer "
                    "(id, tenant_id, branch_id, identity_user_id, customer_type, full_name, "
                    "phone_number, consumer_number) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :identity_user_id, "
                    "'domestic', 'TDT Smoke Customer', :phone, :consumer_number) RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id),
                    "identity_user_id": str(identity_customer_id),
                    "phone": f"+91{uuid.uuid4().int % 10**9:09d}",
                    "consumer_number": f"CN{uuid.uuid4().hex[:10]}",
                },
            )
        ).scalar_one()
        address_id = (
            await conn.execute(
                text(
                    "INSERT INTO customer.customer_address "
                    "(id, tenant_id, customer_id, line_1) "
                    "VALUES (gen_random_uuid(), :tenant_id, :customer_id, '123 Test St') "
                    "RETURNING id"
                ),
                {"tenant_id": str(tenant_id), "customer_id": str(customer_id)},
            )
        ).scalar_one()

        now = datetime.now(UTC)
        order_id = (
            await conn.execute(
                text(
                    "INSERT INTO orders.order "
                    "(id, tenant_id, branch_id, customer_id, address_id, "
                    "delivery_address_line, status, booking_source, requested_date) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :customer_id, "
                    ":address_id, '123 Test St', 'delivered', 'staff', :requested_date) "
                    "RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id),
                    "customer_id": str(customer_id),
                    "address_id": str(address_id),
                    "requested_date": now,
                },
            )
        ).scalar_one()
        for to_status, from_status in (("booked", "draft"), ("delivered", "out_for_delivery")):
            await conn.execute(
                text(
                    "INSERT INTO orders.order_status_history "
                    "(id, order_id, from_status, to_status, changed_by, changed_at) "
                    "VALUES (gen_random_uuid(), :order_id, :from_status, :to_status, "
                    "gen_random_uuid(), :changed_at)"
                ),
                {
                    "order_id": str(order_id),
                    "from_status": from_status,
                    "to_status": to_status,
                    "changed_at": now,
                },
            )

        # tdt_star_rating_bands — TEST FIXTURE, not a real MDG figure.
        config_value = (
            '{"mdg_edition": "TEST-FIXTURE", "bands": '
            '[{"stars": 5, "max_days": 1}, {"stars": 1, "max_days": null}]}'
        )
        await conn.execute(
            text(
                "INSERT INTO tenant.tenant_configuration "
                "(id, tenant_id, config_key, config_value, effective_from) "
                "VALUES (gen_random_uuid(), :tenant_id, 'tdt_star_rating_bands', "
                "CAST(:config_value AS jsonb), '2020-01-01T00:00:00+00:00')"
            ),
            {"tenant_id": str(tenant_id), "config_value": config_value},
        )
    return email, tenant_id


async def _login(client: AsyncClient, *, email: str, password: str) -> str:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token: str = resp.json()["access_token"]
    return token


async def test_live_projection_and_quarterly_rating_smoke(
    client: AsyncClient,
    admin_engine_lpg_test: AsyncEngine,
    integration_settings: Settings,
) -> None:
    password = "correct horse battery staple 42"
    hasher = Argon2PasswordHasher(integration_settings)
    email, _tenant_id = await _seed_manager_tenant_customer_and_order(
        admin_engine_lpg_test, password_hash=hasher.hash(password)
    )
    token = await _login(client, email=email, password=password)
    headers = {"Authorization": f"Bearer {token}"}

    live = await client.get("/api/v1/tdt-rating/live-projection", headers=headers)
    assert live.status_code == 200, live.text
    body = live.json()
    assert body["total_orders"] == 1
    assert body["overall_stars"] == 5  # same-day delivery -> the top test-fixture band
    assert body["distribution"] == [{"stars": 5, "order_count": 1}]

    today = datetime.now(UTC).date()
    quarterly = await client.get(
        "/api/v1/tdt-rating/quarterly",
        # A deliberately wide window (the whole current calendar year) is
        # enough to exercise the endpoint end to end without hand-computing
        # the exact current quarter boundary in a smoke test — the
        # boundary-precision cases already have dedicated coverage in
        # test_tdt_rating_use_case.py.
        params={
            "quarter_start": f"{today.year}-01-01",
            "quarter_end": f"{today.year + 1}-01-01",
        },
        headers=headers,
    )
    assert quarterly.status_code == 200, quarterly.text
    assert quarterly.json()["total_orders"] >= 1


async def test_tdt_read_permission_is_enforced(
    client: AsyncClient,
    admin_engine_lpg_test: AsyncEngine,
    integration_settings: Settings,
) -> None:
    """A role with no `tdt:read` grant (driver) gets a 403, not a silent
    empty result — this endpoint being reachable at all depends on the
    new permission code actually existing and being wired to
    `require_permission`, not just on the use case working."""
    password = "correct horse battery staple 42"
    hasher = Argon2PasswordHasher(integration_settings)
    email = f"{uuid.uuid4().hex}@tdt-smoke-driver.example"
    async with admin_engine_lpg_test.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'TDT Smoke Driver', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"tdt-smoke-drv-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO identity.identity_user "
                "(id, tenant_id, email, password_hash, role) "
                "VALUES (gen_random_uuid(), :tenant_id, :email, :ph, 'driver')"
            ),
            {"tenant_id": str(tenant_id), "email": email, "ph": hasher.hash(password)},
        )

    token = await _login(client, email=email, password=password)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/api/v1/tdt-rating/live-projection", headers=headers)
    assert resp.status_code == 403, resp.text
