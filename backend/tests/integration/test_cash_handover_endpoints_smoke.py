"""Smoke tests for the cash-handover router (R10, `CashShortfallDeclared`),
through the real ASGI stack.

Proves the migration granting `cash_handovers:declare` (a brand-new
permission code — nothing existed to gate this endpoint with before this
change) actually works, and that `expected_amount` reflects real seeded
`orders.proof_of_delivery` data rather than a placeholder.
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
                {"name": tenant_name, "slug": f"cash-smoke-{uuid.uuid4().hex[:10]}"},
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


async def _seed_route_with_cash_delivery(
    engine: AsyncEngine,
    *,
    tenant_id: uuid.UUID,
    amount_collected: str,
    route_status: str = "completed",
) -> tuple[uuid.UUID, uuid.UUID]:
    """Branch -> employee -> driver -> vehicle -> customer -> order ->
    route -> one delivered route_stop with a real cash-payment
    proof-of-delivery row. Returns (driver_id, route_id).
    """
    async with engine.begin() as conn:
        branch_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.branch (id, tenant_id, name) "
                    "VALUES (gen_random_uuid(), :tenant_id, 'Cash Handover Smoke Branch') "
                    "RETURNING id"
                ),
                {"tenant_id": str(tenant_id)},
            )
        ).scalar_one()
        employee_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.employee "
                    "(id, tenant_id, branch_id, employee_code, first_name, last_name, "
                    "phone_number, role, status) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :employee_code, "
                    "'Cash', 'Smoke Driver', '1234567890', 'driver', 'active') "
                    "RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id),
                    "employee_code": f"DRV-{uuid.uuid4().hex[:6]}",
                },
            )
        ).scalar_one()
        driver_id = (
            await conn.execute(
                text(
                    "INSERT INTO delivery.driver "
                    "(id, tenant_id, branch_id, employee_id, license_number) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :employee_id, 'DL123456') "
                    "RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id),
                    "employee_id": str(employee_id),
                },
            )
        ).scalar_one()
        vehicle_id = (
            await conn.execute(
                text(
                    "INSERT INTO delivery.vehicle "
                    "(id, tenant_id, branch_id, registration_number, make, model, capacity_units) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :reg, 'Tata', 'Ace', 50) "
                    "RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id),
                    "reg": f"MH-{uuid.uuid4().hex[:8]}",
                },
            )
        ).scalar_one()
        customer_id = (
            await conn.execute(
                text(
                    "INSERT INTO customer.customer "
                    "(id, tenant_id, branch_id, customer_type, full_name, phone_number, "
                    "consumer_number) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, 'domestic', "
                    "'Cash Handover Smoke Customer', :phone, :consumer_number) RETURNING id"
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
                    "delivery_address_line, status, booking_source, requested_date) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :customer_id, "
                    ":address_id, '1 Smoke Test Rd', 'closed', 'staff', now()) "
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
        route_id = (
            await conn.execute(
                text(
                    "INSERT INTO delivery.route "
                    "(id, tenant_id, branch_id, driver_id, vehicle_id, route_date, status) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :driver_id, :vehicle_id, "
                    "now(), :route_status) RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id),
                    "driver_id": str(driver_id),
                    "vehicle_id": str(vehicle_id),
                    "route_status": route_status,
                },
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO delivery.route_stop "
                "(id, route_id, order_id, sequence_number, status) "
                "VALUES (gen_random_uuid(), :route_id, :order_id, 1, 'delivered')"
            ),
            {"route_id": str(route_id), "order_id": str(order_id)},
        )
        await conn.execute(
            text(
                "INSERT INTO orders.proof_of_delivery "
                "(id, tenant_id, order_id, otp_verified_at, signature_blob_ref, "
                "photo_blob_ref, gps_lat, gps_lng, payment_method, amount_collected, "
                "recorded_by) "
                "VALUES (gen_random_uuid(), :tenant_id, :order_id, now(), 'sig-ref', "
                "'photo-ref', 18.520430, 73.856743, 'cash', :amount_collected, "
                "gen_random_uuid())"
            ),
            {
                "tenant_id": str(tenant_id),
                "order_id": str(order_id),
                "amount_collected": amount_collected,
            },
        )
    return uuid.UUID(str(driver_id)), uuid.UUID(str(route_id))


async def _login(client: AsyncClient, *, email: str, password: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    access_token: str = response.json()["access_token"]
    return access_token


class TestCashHandoverEndpointsThroughTheRealStack:
    async def test_declare_handover_computes_real_expected_amount_and_shortfall(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        hasher = Argon2PasswordHasher(integration_settings)
        email = f"{uuid.uuid4().hex}@cash-smoke.example"
        password = "correct horse battery staple 42"
        tenant_id = await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="agency_admin",
            tenant_name="Cash Handover Smoke Tenant (shortfall)",
        )
        driver_id, route_id = await _seed_route_with_cash_delivery(
            admin_engine_lpg_test, tenant_id=tenant_id, amount_collected="1000.00"
        )

        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}

        response = await real_lifespan_client.post(
            "/api/v1/cash-handovers",
            headers=headers,
            json={
                "driver_id": str(driver_id),
                "route_id": str(route_id),
                "actual_amount": "850.00",
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["expected_amount"] == "1000.00"
        assert body["actual_amount"] == "850.00"
        assert body["shortfall"] == "150.00"

    async def test_declare_handover_matching_amount_has_zero_shortfall(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        hasher = Argon2PasswordHasher(integration_settings)
        email = f"{uuid.uuid4().hex}@cash-smoke.example"
        password = "correct horse battery staple 42"
        tenant_id = await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="agency_admin",
            tenant_name="Cash Handover Smoke Tenant (exact)",
        )
        driver_id, route_id = await _seed_route_with_cash_delivery(
            admin_engine_lpg_test, tenant_id=tenant_id, amount_collected="500.00"
        )

        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}

        response = await real_lifespan_client.post(
            "/api/v1/cash-handovers",
            headers=headers,
            json={
                "driver_id": str(driver_id),
                "route_id": str(route_id),
                "actual_amount": "500.00",
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["shortfall"] == "0.00" or response.json()["shortfall"] == "0"

    async def test_declare_handover_for_someone_elses_route_is_not_found(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        hasher = Argon2PasswordHasher(integration_settings)
        email = f"{uuid.uuid4().hex}@cash-smoke.example"
        password = "correct horse battery staple 42"
        tenant_id = await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="agency_admin",
            tenant_name="Cash Handover Smoke Tenant (mismatch)",
        )
        _driver_id, route_id = await _seed_route_with_cash_delivery(
            admin_engine_lpg_test, tenant_id=tenant_id, amount_collected="500.00"
        )

        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}

        response = await real_lifespan_client.post(
            "/api/v1/cash-handovers",
            headers=headers,
            json={
                "driver_id": str(uuid.uuid4()),
                "route_id": str(route_id),
                "actual_amount": "0",
            },
        )
        assert response.status_code == 404, response.text

    async def test_declare_handover_denied_without_permission(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        """`accountant` is not among `c039189dfbdc`'s granted roles."""
        hasher = Argon2PasswordHasher(integration_settings)
        email = f"{uuid.uuid4().hex}@cash-smoke.example"
        password = "correct horse battery staple 42"
        tenant_id = await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="accountant",
            tenant_name="Cash Handover Smoke Tenant (denied)",
        )
        driver_id, route_id = await _seed_route_with_cash_delivery(
            admin_engine_lpg_test, tenant_id=tenant_id, amount_collected="500.00"
        )

        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}

        response = await real_lifespan_client.post(
            "/api/v1/cash-handovers",
            headers=headers,
            json={
                "driver_id": str(driver_id),
                "route_id": str(route_id),
                "actual_amount": "0",
            },
        )
        assert response.status_code == 403, response.text

    async def test_for_route_view_before_and_after_declaring(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        hasher = Argon2PasswordHasher(integration_settings)
        email = f"{uuid.uuid4().hex}@cash-smoke.example"
        password = "correct horse battery staple 42"
        tenant_id = await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="agency_admin",
            tenant_name="Cash Handover Smoke Tenant (view)",
        )
        driver_id, route_id = await _seed_route_with_cash_delivery(
            admin_engine_lpg_test, tenant_id=tenant_id, amount_collected="750.00"
        )

        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}

        before = await real_lifespan_client.get(
            f"/api/v1/cash-handovers/for-route/{route_id}", headers=headers
        )
        assert before.status_code == 200, before.text
        body = before.json()
        assert body["expected_amount"] == "750.00"
        assert body["cash_stop_count"] == 1
        assert body["route_status"] == "completed"
        assert body["handover"] is None

        declared = await real_lifespan_client.post(
            "/api/v1/cash-handovers",
            headers=headers,
            json={
                "driver_id": str(driver_id),
                "route_id": str(route_id),
                "actual_amount": "750.00",
            },
        )
        assert declared.status_code == 201, declared.text

        after = await real_lifespan_client.get(
            f"/api/v1/cash-handovers/for-route/{route_id}", headers=headers
        )
        assert after.status_code == 200, after.text
        handover = after.json()["handover"]
        assert handover is not None
        assert handover["actual_amount"] == "750.00"
        assert handover["shortfall"] in ("0", "0.00")
        assert handover["handover_number"] is not None

    async def test_second_declaration_for_a_route_is_a_conflict(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        hasher = Argon2PasswordHasher(integration_settings)
        email = f"{uuid.uuid4().hex}@cash-smoke.example"
        password = "correct horse battery staple 42"
        tenant_id = await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="agency_admin",
            tenant_name="Cash Handover Smoke Tenant (dup)",
        )
        driver_id, route_id = await _seed_route_with_cash_delivery(
            admin_engine_lpg_test, tenant_id=tenant_id, amount_collected="300.00"
        )

        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "driver_id": str(driver_id),
            "route_id": str(route_id),
            "actual_amount": "300.00",
        }

        first = await real_lifespan_client.post(
            "/api/v1/cash-handovers", headers=headers, json=payload
        )
        assert first.status_code == 201, first.text

        second = await real_lifespan_client.post(
            "/api/v1/cash-handovers", headers=headers, json=payload
        )
        assert second.status_code == 409, second.text
        assert second.json()["error_code"] == "CONFLICT"

    async def test_declaration_rejected_while_route_is_in_progress(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        hasher = Argon2PasswordHasher(integration_settings)
        email = f"{uuid.uuid4().hex}@cash-smoke.example"
        password = "correct horse battery staple 42"
        tenant_id = await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="agency_admin",
            tenant_name="Cash Handover Smoke Tenant (early)",
        )
        driver_id, route_id = await _seed_route_with_cash_delivery(
            admin_engine_lpg_test,
            tenant_id=tenant_id,
            amount_collected="300.00",
            route_status="in_progress",
        )

        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}

        response = await real_lifespan_client.post(
            "/api/v1/cash-handovers",
            headers=headers,
            json={
                "driver_id": str(driver_id),
                "route_id": str(route_id),
                "actual_amount": "300.00",
            },
        )
        assert response.status_code == 422, response.text
