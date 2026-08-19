"""Smoke tests for the reporting router, through the real ASGI stack.

Until this router was mounted (R7a), `/api/v1/reporting/{sales,gst,drivers,
consumption}` 404'd unconditionally — C7 in `planning/MODULE_STATUS.md`
found the frontend already called all four, `app.py` imported the router
module, but no `app.include_router(reporting.router, ...)` line existed.
These tests prove the mount itself: every endpoint is reachable, enforces
`reports:read`, and its query executes cleanly against the real `rpt`
schema views/materialized views created by
`bab6ab8f401f_create_reporting_schema` — the most likely failure mode for
code that has never been exercised (a typo in a view/column name, a
missing grant). One endpoint (`/sales`, backed by a plain view that
reflects new rows immediately, unlike the three materialized ones) is also
exercised against real seeded data to prove the tenant-scoping `WHERE`
clause actually filters rather than coincidentally returning nothing.

Deeper business-logic coverage for the other three reports (which need a
full order→delivery→invoice lifecycle or cylinder-ledger exchange history
to produce non-empty rows) is R7's job, not this one's.
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


async def _seed_staff_user(
    engine: AsyncEngine, *, email: str, password_hash: str, role: str, tenant_name: str
) -> uuid.UUID:
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), :name, :slug, 'ops@example.com') RETURNING id"
                ),
                {"name": tenant_name, "slug": f"rpt-smoke-{uuid.uuid4().hex[:10]}"},
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
    return uuid.UUID(str(tenant_id))


async def _seed_invoice(engine: AsyncEngine, *, tenant_id: uuid.UUID) -> None:
    """One invoice, feeding `rpt.vw_daily_sales` (a plain view — visible
    immediately, unlike the three materialized ones the other endpoints
    read from).
    """
    async with engine.begin() as conn:
        branch_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.branch (id, tenant_id, name) "
                    "VALUES (gen_random_uuid(), :tenant_id, 'Reporting Smoke Branch') "
                    "RETURNING id"
                ),
                {"tenant_id": str(tenant_id)},
            )
        ).scalar_one()
        customer_id = (
            await conn.execute(
                text(
                    "INSERT INTO customer.customer "
                    "(id, tenant_id, branch_id, customer_type, full_name, phone_number, "
                    "consumer_number) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, 'domestic', "
                    "'Reporting Smoke Customer', :phone, :consumer_number) RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id),
                    "phone": f"9{uuid.uuid4().int % 10**9:09d}",
                    "consumer_number": f"CN-{uuid.uuid4().hex[:8]}",
                },
            )
        ).scalar_one()
        address_id = (
            await conn.execute(
                text(
                    "INSERT INTO customer.customer_address (id, tenant_id, customer_id, line_1) "
                    "VALUES (gen_random_uuid(), :tenant_id, :customer_id, '1 Smoke Test Rd') "
                    "RETURNING id"
                ),
                {"tenant_id": str(tenant_id), "customer_id": str(customer_id)},
            )
        ).scalar_one()
        order_id = (
            await conn.execute(
                text(
                    "INSERT INTO orders.order "
                    "(id, tenant_id, branch_id, customer_id, address_id, "
                    "delivery_address_line, status, booking_source, requested_date, "
                    "total_amount) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :customer_id, "
                    ":address_id, '1 Smoke Test Rd', 'closed', 'staff', now(), 500.00) "
                    "RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id),
                    "customer_id": str(customer_id),
                    "address_id": str(address_id),
                },
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO accounting.invoice "
                "(id, tenant_id, customer_id, order_id, status, subtotal, tax_amount, "
                "total_amount, issued_at) "
                "VALUES (gen_random_uuid(), :tenant_id, :customer_id, :order_id, 'issued', "
                "450.00, 50.00, 500.00, now())"
            ),
            {
                "tenant_id": str(tenant_id),
                "customer_id": str(customer_id),
                "order_id": str(order_id),
            },
        )


async def _login(client: AsyncClient, *, email: str, password: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    access_token: str = response.json()["access_token"]
    return access_token


class TestReportingEndpointsThroughTheRealStack:
    async def test_all_four_endpoints_are_mounted_and_return_empty_lists(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        """Each of the four is a genuine SQL query against a real `rpt.*`
        view/materialized view — an empty-but-200 response for a
        just-seeded tenant proves both the mount (no more 404) and that the
        query itself is syntactically/referentially valid, not just that
        RBAC let the request through.
        """
        email = f"{uuid.uuid4().hex}@rpt-smoke.example"
        password = "correct horse battery staple 42"
        hasher = Argon2PasswordHasher(integration_settings)
        await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="agency_admin",
            tenant_name="Reporting Smoke Tenant (empty)",
        )

        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}
        client = real_lifespan_client

        sales_response = await client.get(
            "/api/v1/reporting/sales?start_date=2020-01-01&end_date=2030-01-01", headers=headers
        )
        assert sales_response.status_code == 200, sales_response.text
        assert sales_response.json() == []

        gst_response = await client.get("/api/v1/reporting/gst", headers=headers)
        assert gst_response.status_code == 200, gst_response.text
        assert gst_response.json() == []

        drivers_response = await client.get(
            "/api/v1/reporting/drivers?start_date=2020-01-01&end_date=2030-01-01", headers=headers
        )
        assert drivers_response.status_code == 200, drivers_response.text
        assert drivers_response.json() == []

        consumption_response = await client.get("/api/v1/reporting/consumption", headers=headers)
        assert consumption_response.status_code == 200, consumption_response.text
        assert consumption_response.json() == []

    async def test_daily_sales_reflects_seeded_invoice_and_is_tenant_scoped(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        hasher = Argon2PasswordHasher(integration_settings)

        email = f"{uuid.uuid4().hex}@rpt-smoke.example"
        password = "correct horse battery staple 42"
        tenant_id = await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="agency_admin",
            tenant_name="Reporting Smoke Tenant (with invoice)",
        )
        await _seed_invoice(admin_engine_lpg_test, tenant_id=tenant_id)

        # A second tenant with its own invoice — proves the response is
        # scoped to the caller's tenant, not every invoice in the database.
        other_email = f"{uuid.uuid4().hex}@rpt-smoke.example"
        other_tenant_id = await _seed_staff_user(
            admin_engine_lpg_test,
            email=other_email,
            password_hash=hasher.hash(password),
            role="agency_admin",
            tenant_name="Reporting Smoke Tenant (other)",
        )
        await _seed_invoice(admin_engine_lpg_test, tenant_id=other_tenant_id)

        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}

        response = await real_lifespan_client.get(
            "/api/v1/reporting/sales?start_date=2020-01-01&end_date=2030-01-01", headers=headers
        )
        assert response.status_code == 200, response.text
        body = response.json()

        assert len(body) == 1, body
        assert body[0]["total_invoices"] == 1
        assert body[0]["total_revenue"] == "500.00"
        assert body[0]["total_tax"] == "50.00"

    async def test_reporting_endpoints_denied_without_reports_read(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        """`driver`/`customer` use the mobile apps, not this surface —
        neither role is granted `reports:read` by `b3f7c1d9e4a2`.
        """
        email = f"{uuid.uuid4().hex}@rpt-smoke.example"
        password = "correct horse battery staple 42"
        hasher = Argon2PasswordHasher(integration_settings)
        await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="driver",
            tenant_name="Reporting Smoke Tenant (denied)",
        )

        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}

        response = await real_lifespan_client.get("/api/v1/reporting/gst", headers=headers)
        assert response.status_code == 403, response.text
