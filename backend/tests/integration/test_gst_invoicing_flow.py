"""GST invoicing through the real stack (QA DA-06, DA-07, DA-12, DA-13).

A delivered order whose cylinder type has no GST rate is not invoiced at
0%: it shows up under "uninvoiced orders" and can be issued once the
cylinder type is classified. Uses the env-var fixtures (`admin_engine`,
`integration_settings`), so it runs against whichever database
`LPG_TEST_*` points at.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from lpg.infrastructure.identity.password_hasher import Argon2PasswordHasher

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

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
    app = create_app(integration_settings)
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
            yield http_client
    get_settings.cache_clear()


async def _seed(
    engine: AsyncEngine, settings: Settings, *, role: str = "accountant"
) -> tuple[uuid.UUID, str, uuid.UUID, uuid.UUID]:
    """A tenant with one staff user and one delivered, uninvoiced order whose
    cylinder type has no GST rate. Returns (tenant, email, order, cylinder type).
    """
    email = f"{uuid.uuid4().hex}@gst-flow.example"
    async with engine.begin() as conn:

        async def scalar(sql: str, **params: object) -> uuid.UUID:
            return uuid.UUID(str((await conn.execute(text(sql), params)).scalar_one()))

        tenant_id = await scalar(
            "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email, legal_name, "
            "gstin, address_line_1, city, state_code, pincode) VALUES (gen_random_uuid(), "
            "'GST Flow Tenant', :slug, 'ops@example.com', 'GST Flow Gas Pvt Ltd', "
            "'36AAFCS4821K1Z6', '1 Main Rd', 'Hyderabad', '36', '500001') RETURNING id",
            slug=f"gst-flow-{uuid.uuid4().hex[:10]}",
        )
        t = {"t": str(tenant_id)}
        user_id = await scalar(
            "INSERT INTO identity.identity_user (id, tenant_id, email, password_hash, role) "
            "VALUES (gen_random_uuid(), :t, :email, :hash, :role) RETURNING id",
            **t,
            email=email,
            hash=Argon2PasswordHasher(settings).hash(PASSWORD),
            role=role,
        )
        await conn.execute(
            text(
                "INSERT INTO identity.identity_user_permission "
                "(id, user_id, permission_id, created_at) "
                "SELECT gen_random_uuid(), :u, rp.permission_id, now() "
                "FROM identity.role_permission rp JOIN identity.role r ON r.id = rp.role_id "
                "WHERE r.code = :role"
            ),
            {"u": str(user_id), "role": role},
        )
        branch_id = await scalar(
            "INSERT INTO tenant.branch (id, tenant_id, name) "
            "VALUES (gen_random_uuid(), :t, 'GST Branch') RETURNING id",
            **t,
        )
        customer_id = await scalar(
            "INSERT INTO customer.customer (id, tenant_id, branch_id, consumer_number, "
            "full_name, phone_number, customer_type, status) VALUES (gen_random_uuid(), :t, "
            ":b, :cn, 'Asha Rao', :phone, 'domestic', 'active') RETURNING id",
            **t,
            b=str(branch_id),
            cn=f"GST{uuid.uuid4().hex[:8]}",
            phone=f"+9198{uuid.uuid4().int % 10**8:08d}",
        )
        address_id = await scalar(
            "INSERT INTO customer.customer_address (id, tenant_id, customer_id, line_1, state) "
            "VALUES (gen_random_uuid(), :t, :c, '1 Pay Rd', 'Telangana') RETURNING id",
            **t,
            c=str(customer_id),
        )
        cylinder_type_id = await scalar(
            "INSERT INTO tenant.cylinder_type (id, tenant_id, name, weight_kg) "
            "VALUES (gen_random_uuid(), :t, 'Domestic 14.2kg', 14.2) RETURNING id",
            **t,
        )
        order_id = await scalar(
            "INSERT INTO orders.order (id, tenant_id, branch_id, customer_id, address_id, "
            "delivery_address_line, status, booking_source, requested_date, total_amount) "
            "VALUES (gen_random_uuid(), :t, :b, :c, :a, '1 Pay Rd', 'delivered', 'staff', "
            "now(), 900.00) RETURNING id",
            **t,
            b=str(branch_id),
            c=str(customer_id),
            a=str(address_id),
        )
        await conn.execute(
            text(
                "INSERT INTO orders.order_line (id, order_id, cylinder_type_id, "
                "quantity_ordered, quantity_delivered, unit_price) "
                "VALUES (gen_random_uuid(), :o, :ct, 2, 2, 450.00)"
            ),
            {"o": str(order_id), "ct": str(cylinder_type_id)},
        )
    return tenant_id, email, order_id, cylinder_type_id


async def _headers(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


class TestGstInvoicingFlow:
    async def test_held_order_is_issued_once_gst_is_configured(
        self, client: AsyncClient, admin_engine: AsyncEngine, integration_settings: Settings
    ) -> None:
        _, email, order_id, cylinder_type_id = await _seed(
            admin_engine, integration_settings, role="agency_admin"
        )
        headers = await _headers(client, email)

        held = await client.get("/api/v1/invoices/uninvoiced-orders", headers=headers)
        assert held.status_code == 200, held.text
        assert [row["order_id"] for row in held.json()] == [str(order_id)]

        blocked = await client.post(
            "/api/v1/invoices", json={"order_id": str(order_id)}, headers=headers
        )
        assert blocked.status_code == 422, blocked.text
        assert blocked.json()["error_code"] == "GST_NOT_CONFIGURED"

        classified = await client.patch(
            f"/api/v1/admin/cylinder-types/{cylinder_type_id}/gst",
            json={"hsn_code": "27111900", "gst_rate_percent": "5"},
            headers=headers,
        )
        assert classified.status_code == 200, classified.text

        issued = await client.post(
            "/api/v1/invoices", json={"order_id": str(order_id)}, headers=headers
        )
        assert issued.status_code == 201, issued.text
        invoice = issued.json()
        assert invoice["invoice_number"].startswith("INV-")
        # 900.00 at 5%, GST-inclusive by default: taxable 900 / 1.05.
        assert invoice["subtotal"] == "857.14"
        assert invoice["tax_amount"] == "42.86"
        assert invoice["total_amount"] == "900.00"
        assert invoice["is_inter_state"] is False
        assert invoice["cgst_amount"] == "21.43"
        assert invoice["sgst_amount"] == "21.43"
        assert invoice["lines"][0]["hsn_code"] == "27111900"
        assert invoice["balance_due"] == "900.00"

        cheque = await client.post(
            f"/api/v1/invoices/{invoice['invoice_id']}/payments",
            json={"method": "cheque", "amount": "900.00"},
            headers=headers,
        )
        assert cheque.status_code == 422, cheque.text
        paid = await client.post(
            f"/api/v1/invoices/{invoice['invoice_id']}/payments",
            json={"method": "cheque", "amount": "900.00", "reference": "000451"},
            headers=headers,
        )
        assert paid.status_code == 201, paid.text
        assert paid.json()["status"] == "paid"
        assert paid.json()["payments"][0]["reference"] == "000451"

        today = datetime.now(UTC).date()
        gstr1 = await client.get(
            "/api/v1/reporting/gst/gstr1",
            params={
                "start_date": (today - timedelta(days=1)).isoformat(),
                "end_date": (today + timedelta(days=1)).isoformat(),
            },
            headers=headers,
        )
        assert gstr1.status_code == 200, gstr1.text

    async def test_uninvoiced_orders_are_tenant_scoped(
        self, client: AsyncClient, admin_engine: AsyncEngine, integration_settings: Settings
    ) -> None:
        _, email, own_order, _ = await _seed(
            admin_engine, integration_settings, role="agency_admin"
        )
        _, _, other_order, _ = await _seed(admin_engine, integration_settings)
        headers = await _headers(client, email)

        held = await client.get("/api/v1/invoices/uninvoiced-orders", headers=headers)
        assert held.status_code == 200, held.text
        ids = {row["order_id"] for row in held.json()}
        assert str(own_order) in ids
        assert str(other_order) not in ids

        foreign = await client.post(
            "/api/v1/invoices", json={"order_id": str(other_order)}, headers=headers
        )
        assert foreign.status_code == 404, foreign.text

    async def test_driver_cannot_issue_invoices(
        self, client: AsyncClient, admin_engine: AsyncEngine, integration_settings: Settings
    ) -> None:
        _, email, order_id, _ = await _seed(admin_engine, integration_settings, role="driver")
        headers = await _headers(client, email)
        response = await client.post(
            "/api/v1/invoices", json={"order_id": str(order_id)}, headers=headers
        )
        assert response.status_code == 403, response.text
