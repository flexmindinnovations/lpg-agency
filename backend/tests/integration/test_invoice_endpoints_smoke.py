"""Smoke tests for the invoice router, through the real ASGI stack.

C4 in `planning/MODULE_STATUS.md` found `complaint`, `employee`, `invoice` and
`reporting` shipped with zero test files. This file is `invoice`'s share of
R7 (`reporting`'s own share landed as R7a).

Exercising `GET /invoices`/`GET /invoices/{id}` against a real seeded invoice
surfaced a genuine, previously-uncaught bug: `_invoice_to_response` called
`InvoiceResponse.model_validate(invoice)`, but the domain `Invoice`/
`InvoiceLine` objects only expose `.id` (from `Entity`), not the
`invoice_id`/`line_id` field names the committed schema — and the frontend's
generated client and `feature-invoices.ts` — already depend on. Every call to
either endpoint failed Pydantic validation on any real invoice. Fixed in
`api/v1/routers/invoice.py` by building the response field-by-field, matching
`_order_to_response`'s convention, rather than relying on `model_validate`.

There is no `POST /invoices` — invoice generation
(`GenerateInvoiceForOrderUseCase`) is not exposed via this router; it is
triggered internally off order-delivery. Invoices here are seeded directly
via SQL, mirroring `test_reporting_endpoints_smoke.py`'s `_seed_invoice`.
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
                {"name": tenant_name, "slug": f"invoice-smoke-{uuid.uuid4().hex[:10]}"},
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


async def _seed_invoice(engine: AsyncEngine, *, tenant_id: uuid.UUID) -> uuid.UUID:
    """One invoice with one line, via a full branch->customer->address->order
    chain — mirrors `test_reporting_endpoints_smoke.py`'s `_seed_invoice`
    (there is no `POST /invoices` to create one through the API).
    """
    async with engine.begin() as conn:
        branch_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.branch (id, tenant_id, name) "
                    "VALUES (gen_random_uuid(), :tenant_id, 'Invoice Smoke Branch') "
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
                    "'Invoice Smoke Customer', :phone, :consumer_number) RETURNING id"
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
        cylinder_type_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.cylinder_type (id, tenant_id, name, weight_kg) "
                    "VALUES (gen_random_uuid(), :tenant_id, 'Invoice Smoke 14.2kg', 14.2) "
                    "RETURNING id"
                ),
                {"tenant_id": str(tenant_id)},
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
        invoice_id = (
            await conn.execute(
                text(
                    "INSERT INTO accounting.invoice "
                    "(id, tenant_id, customer_id, order_id, status, subtotal, tax_amount, "
                    "total_amount, issued_at) "
                    "VALUES (gen_random_uuid(), :tenant_id, :customer_id, :order_id, 'issued', "
                    "450.00, 50.00, 500.00, now()) RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "customer_id": str(customer_id),
                    "order_id": str(order_id),
                },
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO accounting.invoice_line "
                "(id, invoice_id, cylinder_type_id, quantity, unit_price, subtotal, "
                "tax_amount, total_amount) "
                "VALUES (gen_random_uuid(), :invoice_id, :cylinder_type_id, 2, 225.00, "
                "450.00, 50.00, 500.00)"
            ),
            {"invoice_id": str(invoice_id), "cylinder_type_id": str(cylinder_type_id)},
        )
    return uuid.UUID(str(invoice_id))


async def _login(client: AsyncClient, *, email: str, password: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    access_token: str = response.json()["access_token"]
    return access_token


class TestInvoiceEndpointsThroughTheRealStack:
    async def test_get_invoice_returns_correctly_shaped_response(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        hasher = Argon2PasswordHasher(integration_settings)
        email = f"{uuid.uuid4().hex}@invoice-smoke.example"
        password = "correct horse battery staple 42"
        tenant_id = await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="accountant",
            tenant_name="Invoice Smoke Tenant (get)",
        )
        invoice_id = await _seed_invoice(admin_engine_lpg_test, tenant_id=tenant_id)

        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}

        response = await real_lifespan_client.get(
            f"/api/v1/invoices/{invoice_id}", headers=headers
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["invoice_id"] == str(invoice_id)
        assert body["status"] == "issued"
        assert body["total_amount"] == "500.00"
        assert len(body["lines"]) == 1
        assert body["lines"][0]["quantity"] == 2

    async def test_list_invoices_is_tenant_scoped(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        hasher = Argon2PasswordHasher(integration_settings)
        password = "correct horse battery staple 42"

        email = f"{uuid.uuid4().hex}@invoice-smoke.example"
        tenant_id = await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="accountant",
            tenant_name="Invoice Smoke Tenant (list, own)",
        )
        await _seed_invoice(admin_engine_lpg_test, tenant_id=tenant_id)

        other_email = f"{uuid.uuid4().hex}@invoice-smoke.example"
        other_tenant_id = await _seed_staff_user(
            admin_engine_lpg_test,
            email=other_email,
            password_hash=hasher.hash(password),
            role="accountant",
            tenant_name="Invoice Smoke Tenant (list, other)",
        )
        await _seed_invoice(admin_engine_lpg_test, tenant_id=other_tenant_id)

        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}

        response = await real_lifespan_client.get("/api/v1/invoices", headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1

    async def test_get_unknown_invoice_returns_404(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        hasher = Argon2PasswordHasher(integration_settings)
        email = f"{uuid.uuid4().hex}@invoice-smoke.example"
        password = "correct horse battery staple 42"
        await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="accountant",
            tenant_name="Invoice Smoke Tenant (404)",
        )
        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}

        response = await real_lifespan_client.get(
            f"/api/v1/invoices/{uuid.uuid4()}", headers=headers
        )
        assert response.status_code == 404, response.text

    async def test_invoice_endpoints_denied_without_invoices_read(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        """`dispatcher` is not among `b9248bf4b34f`'s granted roles."""
        hasher = Argon2PasswordHasher(integration_settings)
        email = f"{uuid.uuid4().hex}@invoice-smoke.example"
        password = "correct horse battery staple 42"
        await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="dispatcher",
            tenant_name="Invoice Smoke Tenant (denied)",
        )
        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}

        response = await real_lifespan_client.get("/api/v1/invoices", headers=headers)
        assert response.status_code == 403, response.text
