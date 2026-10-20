"""Online payments (ADR-053) through the real ASGI stack and PostgreSQL.

Razorpay itself is never called: `get_payment_gateway` is overridden with a
`RazorpayPaymentGateway` whose two outbound calls are stubbed, so webhook
signature verification and event parsing are the real adapter code.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from lpg.application.accounting.payment_gateway import PaymentLink, PaymentLinkStatus
from lpg.infrastructure.identity.password_hasher import Argon2PasswordHasher
from lpg.infrastructure.payments.razorpay import RazorpayPaymentGateway

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.application.accounting.payment_gateway import PaymentLinkRequest
    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration

WEBHOOK_SECRET = "whsec_integration"
PASSWORD = "correct horse battery staple 42"


class _StubbedRazorpay(RazorpayPaymentGateway):
    def __init__(self) -> None:
        super().__init__(
            key_id="rzp_test_integration",
            key_secret="secret",
            webhook_secret=WEBHOOK_SECRET,
            api_base_url="https://api.razorpay.invalid/v1",
            callback_url="",
            timeout_seconds=1,
        )
        self.requests: list[PaymentLinkRequest] = []
        self.remote_status = "created"

    async def create_payment_link(self, request: PaymentLinkRequest) -> PaymentLink:
        self.requests.append(request)
        link_id = f"plink_{uuid.uuid4().hex[:14]}"
        return PaymentLink(link_id=link_id, short_url=f"https://rzp.io/i/{link_id}")

    async def fetch_payment_link(self, link_id: str) -> PaymentLinkStatus:
        return PaymentLinkStatus(
            link_id=link_id, status=self.remote_status, provider_payment_id="pay_refresh"
        )


@pytest.fixture
def gateway() -> _StubbedRazorpay:
    return _StubbedRazorpay()


@pytest.fixture
async def client(
    integration_settings: Settings,
    postgres_available: bool,
    redis_available: bool,
    monkeypatch: pytest.MonkeyPatch,
    gateway: _StubbedRazorpay,
) -> AsyncIterator[AsyncClient]:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable")
    if not redis_available:
        pytest.skip("Redis is not reachable")

    monkeypatch.setenv("LPG_ENVIRONMENT", "local")
    monkeypatch.setenv("LPG_DATABASE_URL", str(integration_settings.database_url))
    monkeypatch.setenv("LPG_REDIS_URL", str(integration_settings.redis_url))

    from lpg.api.app import create_app
    from lpg.api.v1.dependencies.payments import get_payment_gateway
    from lpg.config.settings import get_settings

    get_settings.cache_clear()
    app: FastAPI = create_app(integration_settings)
    app.dependency_overrides[get_payment_gateway] = lambda: gateway
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


async def _seed_tenant_with_staff(
    engine: AsyncEngine, settings: Settings, *, role: str = "accountant"
) -> tuple[uuid.UUID, str]:
    email = f"{uuid.uuid4().hex}@online-payment.example"
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'Online Payment Tenant', :slug, "
                    "'ops@example.com') RETURNING id"
                ),
                {"slug": f"online-pay-{uuid.uuid4().hex[:10]}"},
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


async def _seed_order(
    engine: AsyncEngine,
    *,
    tenant_id: uuid.UUID,
    status: str = "confirmed",
    gst_percent: int | None = None,
    with_invoice: bool = False,
) -> uuid.UUID:
    """A confirmed order: 2 cylinders at 450.00, optionally already invoiced."""
    params = {"tenant_id": str(tenant_id)}
    async with engine.begin() as conn:

        async def scalar(sql: str, **extra: object) -> object:
            return (await conn.execute(text(sql), {**params, **extra})).scalar_one()

        branch_id = await scalar(
            "INSERT INTO tenant.branch (id, tenant_id, name) "
            "VALUES (gen_random_uuid(), :tenant_id, 'Pay Branch') RETURNING id"
        )
        customer_id = await scalar(
            "INSERT INTO customer.customer (id, tenant_id, branch_id, customer_type, full_name, "
            "phone_number, consumer_number) VALUES (gen_random_uuid(), :tenant_id, :branch_id, "
            "'domestic', 'Pay Customer', :phone, :consumer) RETURNING id",
            branch_id=str(branch_id),
            phone=f"+919{uuid.uuid4().int % 10**9:09d}",
            consumer=f"CN-{uuid.uuid4().hex[:8]}",
        )
        address_id = await scalar(
            "INSERT INTO customer.customer_address (id, tenant_id, customer_id, line_1) "
            "VALUES (gen_random_uuid(), :tenant_id, :customer_id, '1 Pay Rd') RETURNING id",
            customer_id=str(customer_id),
        )
        # GST must be configured before anything can be invoiced or prepaid
        # (DA-06). Without `gst_percent` the cylinder type itself is
        # classified at 0%; with it, the legacy tenant-wide rate applies.
        cylinder_type_id = await scalar(
            "INSERT INTO tenant.cylinder_type (id, tenant_id, name, weight_kg, hsn_code, "
            "gst_rate_percent) VALUES (gen_random_uuid(), :tenant_id, 'Pay 14.2kg', 14.2, "
            "'27111900', CASE WHEN :classified THEN 0 END) RETURNING id",
            classified=gst_percent is None,
        )
        order_id = await scalar(
            "INSERT INTO orders.order (id, tenant_id, branch_id, customer_id, address_id, "
            "delivery_address_line, status, booking_source, requested_date, total_amount) "
            "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :customer_id, :address_id, "
            "'1 Pay Rd', :status, 'staff', now(), 900.00) RETURNING id",
            branch_id=str(branch_id),
            customer_id=str(customer_id),
            address_id=str(address_id),
            status=status,
        )
        await conn.execute(
            text(
                "INSERT INTO orders.order_line (id, order_id, cylinder_type_id, "
                "quantity_ordered, unit_price) VALUES (gen_random_uuid(), :order_id, :ct, 2, 450)"
            ),
            {"order_id": str(order_id), "ct": str(cylinder_type_id)},
        )
        if gst_percent is not None:
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant_configuration (tenant_id, config_key, "
                    "config_value, effective_from) VALUES (:tenant_id, 'gst_rate_percent', "
                    "to_jsonb(CAST(:gst AS text)), now() - interval '1 day')"
                ),
                {**params, "gst": str(gst_percent)},
            )
        if with_invoice:
            invoice_id = await scalar(
                "INSERT INTO accounting.invoice (id, tenant_id, customer_id, order_id, status, "
                "subtotal, tax_amount, total_amount, issued_at) VALUES (gen_random_uuid(), "
                ":tenant_id, :customer_id, :order_id, 'issued', 900, 0, 900, now()) RETURNING id",
                customer_id=str(customer_id),
                order_id=str(order_id),
            )
            await conn.execute(
                text(
                    "INSERT INTO accounting.invoice_line (id, invoice_id, cylinder_type_id, "
                    "quantity, unit_price, subtotal, tax_amount, total_amount) VALUES "
                    "(gen_random_uuid(), :invoice_id, :ct, 2, 450, 900, 0, 900)"
                ),
                {"invoice_id": str(invoice_id), "ct": str(cylinder_type_id)},
            )
    return uuid.UUID(str(order_id))


async def _headers(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _webhook(event: str, *, link_id: str, tenant_id: uuid.UUID) -> tuple[bytes, dict[str, str]]:
    body = json.dumps(
        {
            "event": event,
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": link_id,
                        "status": event.split(".")[-1],
                        "notes": {"tenant_id": str(tenant_id)},
                    }
                },
                "payment": {
                    "entity": {"id": "pay_webhook", "method": "upi", "created_at": 1760000000}
                },
            },
        }
    ).encode()
    signature = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return body, {"X-Razorpay-Signature": signature, "Content-Type": "application/json"}


class TestOnlinePaymentFlow:
    async def test_prepay_link_then_webhook_marks_paid(
        self,
        client: AsyncClient,
        admin: AsyncEngine,
        integration_settings: Settings,
        gateway: _StubbedRazorpay,
    ) -> None:
        tenant_id, email = await _seed_tenant_with_staff(admin, integration_settings)
        order_id = await _seed_order(admin, tenant_id=tenant_id, gst_percent=5)
        headers = await _headers(client, email)

        created = await client.post(f"/api/v1/orders/{order_id}/payment-links", headers=headers)
        assert created.status_code == 201, created.text
        body = created.json()
        assert Decimal(body["amount"]) == Decimal("945.00")
        assert body["status"] == "created"
        assert body["payment_url"].startswith("https://rzp.io/i/plink_")
        assert gateway.requests[0].notes["tenant_id"] == str(tenant_id)

        again = await client.post(f"/api/v1/orders/{order_id}/payment-links", headers=headers)
        assert again.json()["online_payment_id"] == body["online_payment_id"]
        assert len(gateway.requests) == 1

        link_id = body["payment_url"].rsplit("/", 1)[-1]
        payload, webhook_headers = _webhook(
            "payment_link.paid", link_id=link_id, tenant_id=tenant_id
        )
        hook = await client.post(
            "/api/v1/payments/razorpay/webhook", content=payload, headers=webhook_headers
        )
        assert hook.status_code == 200, hook.text
        # Redelivery is harmless.
        hook = await client.post(
            "/api/v1/payments/razorpay/webhook", content=payload, headers=webhook_headers
        )
        assert hook.status_code == 200, hook.text

        listed = await client.get(f"/api/v1/orders/{order_id}/online-payments", headers=headers)
        assert listed.status_code == 200, listed.text
        [item] = listed.json()["items"]
        assert item["status"] == "paid"
        assert item["payment_method"] == "upi"
        assert item["applied_to_invoice"] is False

        nothing_due = await client.post(f"/api/v1/orders/{order_id}/payment-links", headers=headers)
        assert nothing_due.status_code == 409, nothing_due.text

    async def test_invoiced_order_is_settled_on_the_invoice(
        self,
        client: AsyncClient,
        admin: AsyncEngine,
        integration_settings: Settings,
        gateway: _StubbedRazorpay,
    ) -> None:
        tenant_id, email = await _seed_tenant_with_staff(admin, integration_settings)
        order_id = await _seed_order(
            admin, tenant_id=tenant_id, status="delivered", with_invoice=True
        )
        headers = await _headers(client, email)

        created = await client.post(f"/api/v1/orders/{order_id}/payment-links", headers=headers)
        assert created.status_code == 201, created.text
        assert Decimal(created.json()["amount"]) == Decimal("900.00")
        assert created.json()["invoice_id"] is not None

        gateway.remote_status = "paid"
        refreshed = await client.post(
            f"/api/v1/online-payments/{created.json()['online_payment_id']}/refresh",
            headers=headers,
        )
        assert refreshed.status_code == 200, refreshed.text
        assert refreshed.json()["status"] == "paid"
        assert refreshed.json()["applied_to_invoice"] is True

        invoice = await client.get(
            f"/api/v1/invoices/{created.json()['invoice_id']}", headers=headers
        )
        assert invoice.status_code == 200, invoice.text
        assert invoice.json()["status"] == "paid"
        assert [p["method"] for p in invoice.json()["payments"]] == ["online_gateway"]

    async def test_webhook_with_bad_signature_is_rejected(self, client: AsyncClient) -> None:
        payload, _ = _webhook("payment_link.paid", link_id="plink_x", tenant_id=uuid.uuid4())
        response = await client.post(
            "/api/v1/payments/razorpay/webhook",
            content=payload,
            headers={"X-Razorpay-Signature": "0" * 64},
        )
        assert response.status_code == 400

    async def test_webhook_cannot_reach_another_tenants_payment(
        self,
        client: AsyncClient,
        admin: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        tenant_id, email = await _seed_tenant_with_staff(admin, integration_settings)
        order_id = await _seed_order(admin, tenant_id=tenant_id)
        headers = await _headers(client, email)
        created = await client.post(f"/api/v1/orders/{order_id}/payment-links", headers=headers)
        link_id = created.json()["payment_url"].rsplit("/", 1)[-1]

        # Validly signed, but naming a different tenant: RLS hides the row.
        other_tenant_id, _ = await _seed_tenant_with_staff(admin, integration_settings)
        payload, webhook_headers = _webhook(
            "payment_link.paid", link_id=link_id, tenant_id=other_tenant_id
        )
        hook = await client.post(
            "/api/v1/payments/razorpay/webhook", content=payload, headers=webhook_headers
        )
        assert hook.status_code == 200

        listed = await client.get(f"/api/v1/orders/{order_id}/online-payments", headers=headers)
        assert listed.json()["items"][0]["status"] == "created"

    async def test_other_tenant_cannot_create_link_for_order(
        self,
        client: AsyncClient,
        admin: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        tenant_id, _ = await _seed_tenant_with_staff(admin, integration_settings)
        order_id = await _seed_order(admin, tenant_id=tenant_id)
        _, other_email = await _seed_tenant_with_staff(admin, integration_settings)
        headers = await _headers(client, other_email)

        response = await client.post(f"/api/v1/orders/{order_id}/payment-links", headers=headers)
        assert response.status_code == 404, response.text

    async def test_driver_cannot_create_payment_links(
        self,
        client: AsyncClient,
        admin: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        tenant_id, email = await _seed_tenant_with_staff(
            admin, integration_settings, role="warehouse_staff"
        )
        order_id = await _seed_order(admin, tenant_id=tenant_id)
        headers = await _headers(client, email)

        response = await client.post(f"/api/v1/orders/{order_id}/payment-links", headers=headers)
        assert response.status_code == 403, response.text


class TestPrepaymentLandsOnGeneratedInvoice:
    async def test_invoice_generated_at_delivery_carries_the_prepayment(
        self,
        client: AsyncClient,
        admin: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        from datetime import UTC, datetime

        from lpg.domain.order.order import CylinderDelivered
        from lpg.infrastructure.events.accounting_handlers import (
            _generate_invoice_for_delivered_order,
        )
        from lpg.infrastructure.persistence.database import Database

        tenant_id, email = await _seed_tenant_with_staff(admin, integration_settings)
        order_id = await _seed_order(admin, tenant_id=tenant_id)
        headers = await _headers(client, email)
        created = await client.post(f"/api/v1/orders/{order_id}/payment-links", headers=headers)
        link_id = created.json()["payment_url"].rsplit("/", 1)[-1]
        payload, webhook_headers = _webhook(
            "payment_link.paid", link_id=link_id, tenant_id=tenant_id
        )
        await client.post(
            "/api/v1/payments/razorpay/webhook", content=payload, headers=webhook_headers
        )

        async with admin.begin() as conn:
            customer_id = (
                await conn.execute(
                    text(
                        "UPDATE orders.order SET status = 'delivered' WHERE id = :id "
                        "RETURNING customer_id"
                    ),
                    {"id": str(order_id)},
                )
            ).scalar_one()
            await conn.execute(
                text("UPDATE orders.order_line SET quantity_delivered = 2 WHERE order_id = :id"),
                {"id": str(order_id)},
            )

        database = Database(integration_settings)
        database.connect()
        try:
            await _generate_invoice_for_delivered_order(
                database,
                CylinderDelivered(
                    order_id=order_id,
                    tenant_id=tenant_id,
                    customer_id=uuid.UUID(str(customer_id)),
                    route_stop_id=None,
                    delivered_at=datetime.now(UTC),
                ),
            )
        finally:
            await database.disconnect()

        invoices = await client.get(f"/api/v1/invoices?order_id={order_id}", headers=headers)
        [invoice] = invoices.json()["items"]
        assert invoice["status"] == "paid"
        assert [p["method"] for p in invoice["payments"]] == ["online_gateway"]

        listed = await client.get(f"/api/v1/orders/{order_id}/online-payments", headers=headers)
        assert listed.json()["items"][0]["applied_to_invoice"] is True
