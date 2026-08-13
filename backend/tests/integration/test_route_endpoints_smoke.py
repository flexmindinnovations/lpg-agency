"""One happy path per route router endpoint, through the real ASGI stack.

Covers `POST /routes` (plan), `GET /routes` (list), `GET /routes/{id}`,
`GET /routes/active-for-driver/{driver_id}`, `POST /routes/{id}/assign-order`,
`POST /routes/{id}/load`, `PATCH /routes/{id}/status`, and
`POST /routes/{id}/reconcile` (both the `409 ROUTE_RECONCILIATION_PENDING`
case and the success case once an approved reconciliation exists) — plus the
`in_progress -> completed` auto-completion (`docs/data/08-state-machines.md`
§3) that fires once a route's last stop resolves.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from lpg.api.v1.dependencies.identity import get_otp_delivery
from lpg.infrastructure.identity.password_hasher import Argon2PasswordHasher

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration


class _CapturingOtpDelivery:
    """Test double for `OtpDeliveryPort` — captures the code instead of
    logging it, since `/depart` never returns it in the response body.
    """

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send(self, phone_number: str, code: str) -> None:
        self.sent.append((phone_number, code))


@dataclass
class _AppAndClient:
    app: FastAPI
    client: AsyncClient
    otp_delivery: _CapturingOtpDelivery


@pytest.fixture
async def stack(
    integration_settings: Settings,
    postgres_available: bool,
    redis_available: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[_AppAndClient]:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable")
    if not redis_available:
        pytest.skip("Redis is not reachable")

    monkeypatch.setenv("LPG_ENVIRONMENT", "local")
    monkeypatch.setenv("LPG_DATABASE_URL", str(integration_settings.database_url))
    monkeypatch.setenv("LPG_REDIS_URL", str(integration_settings.redis_url))

    import redis.asyncio as redis_asyncio

    redis_client = redis_asyncio.from_url(  # type: ignore[no-untyped-call]
        str(integration_settings.redis_url)
    )
    await redis_client.flushdb()
    await redis_client.aclose()

    from lpg.api.app import create_app
    from lpg.config.settings import get_settings

    get_settings.cache_clear()
    app: FastAPI = create_app(integration_settings)
    otp_delivery = _CapturingOtpDelivery()
    app.dependency_overrides[get_otp_delivery] = lambda: otp_delivery
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
            yield _AppAndClient(app=app, client=http_client, otp_delivery=otp_delivery)
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


# ==========================================================================
# Seed helpers
# ==========================================================================


async def _seed_tenant_and_branch(
    engine: AsyncEngine, *, name: str = "Route Smoke Tenant"
) -> tuple[uuid.UUID, uuid.UUID]:
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), :name, :slug, 'ops@example.com') RETURNING id"
                ),
                {"name": name, "slug": f"route-smoke-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
        branch_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.branch (id, tenant_id, name) "
                    "VALUES (gen_random_uuid(), :tenant_id, 'Main Branch') RETURNING id"
                ),
                {"tenant_id": str(tenant_id)},
            )
        ).scalar_one()
    return uuid.UUID(str(tenant_id)), uuid.UUID(str(branch_id))


async def _seed_staff_user(
    engine: AsyncEngine,
    *,
    tenant_id: uuid.UUID,
    branch_id: uuid.UUID | None,
    email: str,
    password_hash: str,
    role: str,
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO identity.identity_user "
                "(id, tenant_id, branch_id, email, password_hash, role) "
                "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :email, :password_hash, :role)"
            ),
            {
                "tenant_id": str(tenant_id),
                "branch_id": str(branch_id) if branch_id else None,
                "email": email,
                "password_hash": password_hash,
                "role": role,
            },
        )


async def _seed_driver(
    engine: AsyncEngine,
    *,
    tenant_id: uuid.UUID,
    branch_id: uuid.UUID,
    email: str,
    password_hash: str,
) -> uuid.UUID:
    async with engine.begin() as conn:
        identity_user_id = (
            await conn.execute(
                text(
                    "INSERT INTO identity.identity_user "
                    "(id, tenant_id, branch_id, email, password_hash, role) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :email, :password_hash, "
                    "'driver') RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id),
                    "email": email,
                    "password_hash": password_hash,
                },
            )
        ).scalar_one()
        driver_id = (
            await conn.execute(
                text(
                    "INSERT INTO delivery.driver "
                    "(id, tenant_id, branch_id, identity_user_id, employee_code, license_number) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :identity_user_id, "
                    ":employee_code, 'DL123456') RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id),
                    "identity_user_id": str(identity_user_id),
                    "employee_code": f"EMP{uuid.uuid4().hex[:8]}",
                },
            )
        ).scalar_one()
    return uuid.UUID(str(driver_id))


async def _seed_vehicle(
    engine: AsyncEngine, *, tenant_id: uuid.UUID, branch_id: uuid.UUID
) -> uuid.UUID:
    async with engine.begin() as conn:
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
    return uuid.UUID(str(vehicle_id))


async def _seed_cylinder_type(engine: AsyncEngine, *, tenant_id: uuid.UUID) -> uuid.UUID:
    async with engine.begin() as conn:
        cylinder_type_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.cylinder_type (id, tenant_id, name, weight_kg) "
                    "VALUES (gen_random_uuid(), :tenant_id, '14.2kg', 14.2) RETURNING id"
                ),
                {"tenant_id": str(tenant_id)},
            )
        ).scalar_one()
    return uuid.UUID(str(cylinder_type_id))


async def _seed_warehouse(
    engine: AsyncEngine, *, tenant_id: uuid.UUID, branch_id: uuid.UUID
) -> uuid.UUID:
    async with engine.begin() as conn:
        warehouse_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.warehouse "
                    "(id, tenant_id, branch_id, name, address_line) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, 'Main WH', '1 Depot Rd') "
                    "RETURNING id"
                ),
                {"tenant_id": str(tenant_id), "branch_id": str(branch_id)},
            )
        ).scalar_one()
    return uuid.UUID(str(warehouse_id))


async def _seed_warehouse_stock(
    engine: AsyncEngine,
    *,
    tenant_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    cylinder_type_id: uuid.UUID,
    quantity: int,
) -> None:
    async with engine.begin() as conn:
        location_id = (
            await conn.execute(
                text(
                    "INSERT INTO inventory.inventory_location "
                    "(id, tenant_id, location_type, location_ref_id) "
                    "VALUES (gen_random_uuid(), :tenant_id, 'warehouse', :warehouse_id) "
                    "RETURNING id"
                ),
                {"tenant_id": str(tenant_id), "warehouse_id": str(warehouse_id)},
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO inventory.inventory_balance "
                "(id, tenant_id, inventory_location_id, cylinder_type_id, status, quantity) "
                "VALUES (gen_random_uuid(), :tenant_id, :location_id, :cylinder_type_id, "
                "'filled', :quantity)"
            ),
            {
                "tenant_id": str(tenant_id),
                "location_id": str(location_id),
                "cylinder_type_id": str(cylinder_type_id),
                "quantity": quantity,
            },
        )


async def _seed_customer(
    engine: AsyncEngine,
    *,
    tenant_id: uuid.UUID,
    branch_id: uuid.UUID,
    email: str,
    password_hash: str,
) -> tuple[uuid.UUID, uuid.UUID]:
    async with engine.begin() as conn:
        identity_user_id = (
            await conn.execute(
                text(
                    "INSERT INTO identity.identity_user "
                    "(id, tenant_id, branch_id, email, password_hash, role) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :email, :password_hash, "
                    "'customer') RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id),
                    "email": email,
                    "password_hash": password_hash,
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
                    "'domestic', 'Route Smoke Customer', :phone, :consumer_number) RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id),
                    "identity_user_id": str(identity_user_id),
                    "phone": f"+91{uuid.uuid4().int % 10**9:09d}",
                    "consumer_number": f"CN{uuid.uuid4().hex[:10]}",
                },
            )
        ).scalar_one()
        address_id = (
            await conn.execute(
                text(
                    "INSERT INTO customer.customer_address "
                    "(id, tenant_id, customer_id, address_line) "
                    "VALUES (gen_random_uuid(), :tenant_id, :customer_id, '123 Test St') "
                    "RETURNING id"
                ),
                {"tenant_id": str(tenant_id), "customer_id": str(customer_id)},
            )
        ).scalar_one()
    return uuid.UUID(str(customer_id)), uuid.UUID(str(address_id))


async def _seed_price_list(
    engine: AsyncEngine, *, tenant_id: uuid.UUID, cylinder_type_id: uuid.UUID, price: Decimal
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO tenant.price_list "
                "(id, tenant_id, cylinder_type_id, customer_type, branch_id, price, "
                "effective_from) "
                "VALUES (gen_random_uuid(), :tenant_id, :cylinder_type_id, 'domestic', NULL, "
                ":price, :effective_from)"
            ),
            {
                "tenant_id": str(tenant_id),
                "cylinder_type_id": str(cylinder_type_id),
                "price": str(price),
                "effective_from": datetime.now(UTC) - timedelta(days=1),
            },
        )


async def _login(client: AsyncClient, *, email: str, password: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    access_token: str = response.json()["access_token"]
    return access_token


def _settings_for_hasher() -> Settings:
    from lpg.config.settings import Settings

    return Settings(environment="local", log_json=False)


@dataclass
class _Fixtures:
    tenant_id: uuid.UUID
    branch_id: uuid.UUID
    admin_token: str
    driver_id: uuid.UUID
    driver_token: str
    vehicle_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    warehouse_id: uuid.UUID
    customer_id: uuid.UUID
    address_id: uuid.UUID


async def _seed_full_fixture_set(client: AsyncClient, engine: AsyncEngine) -> _Fixtures:
    hasher = Argon2PasswordHasher(_settings_for_hasher())
    tenant_id, branch_id = await _seed_tenant_and_branch(engine)

    admin_email = f"{uuid.uuid4().hex}@route-smoke.example"
    admin_password = "correct horse battery staple 42"
    await _seed_staff_user(
        engine,
        tenant_id=tenant_id,
        branch_id=branch_id,
        email=admin_email,
        password_hash=hasher.hash(admin_password),
        role="agency_admin",
    )
    admin_token = await _login(client, email=admin_email, password=admin_password)

    driver_email = f"{uuid.uuid4().hex}@route-smoke.example"
    driver_password = "correct horse battery staple 43"
    driver_id = await _seed_driver(
        engine,
        tenant_id=tenant_id,
        branch_id=branch_id,
        email=driver_email,
        password_hash=hasher.hash(driver_password),
    )
    driver_token = await _login(client, email=driver_email, password=driver_password)

    vehicle_id = await _seed_vehicle(engine, tenant_id=tenant_id, branch_id=branch_id)
    cylinder_type_id = await _seed_cylinder_type(engine, tenant_id=tenant_id)
    warehouse_id = await _seed_warehouse(engine, tenant_id=tenant_id, branch_id=branch_id)
    await _seed_warehouse_stock(
        engine,
        tenant_id=tenant_id,
        warehouse_id=warehouse_id,
        cylinder_type_id=cylinder_type_id,
        quantity=100,
    )
    await _seed_price_list(
        engine, tenant_id=tenant_id, cylinder_type_id=cylinder_type_id, price=Decimal("950.00")
    )
    customer_email = f"{uuid.uuid4().hex}@route-smoke.example"
    customer_id, address_id = await _seed_customer(
        engine,
        tenant_id=tenant_id,
        branch_id=branch_id,
        email=customer_email,
        password_hash=hasher.hash("correct horse battery staple 44"),
    )

    return _Fixtures(
        tenant_id=tenant_id,
        branch_id=branch_id,
        admin_token=admin_token,
        driver_id=driver_id,
        driver_token=driver_token,
        vehicle_id=vehicle_id,
        cylinder_type_id=cylinder_type_id,
        warehouse_id=warehouse_id,
        customer_id=customer_id,
        address_id=address_id,
    )


async def _create_and_confirm_order(
    client: AsyncClient, fixtures: _Fixtures, headers: dict[str, str], *, quantity: int = 2
) -> dict[str, Any]:
    create_payload = {
        "branch_id": str(fixtures.branch_id),
        "customer_id": str(fixtures.customer_id),
        "address_id": str(fixtures.address_id),
        "delivery_address": {"address_line": "123 Test St"},
        "booking_source": "staff",
        "requested_date": datetime.now(UTC).isoformat(),
        "lines": [{"cylinder_type_id": str(fixtures.cylinder_type_id), "quantity": quantity}],
    }
    create_response = await client.post(
        "/api/v1/orders",
        json=create_payload,
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert create_response.status_code == 201, create_response.text
    order = create_response.json()

    confirm_response = await client.post(f"/api/v1/orders/{order['id']}/confirm", headers=headers)
    assert confirm_response.status_code == 200, confirm_response.text
    result: dict[str, Any] = confirm_response.json()
    return result


class TestRouteEndpointsThroughRealStack:
    async def test_route_lifecycle_smoke(
        self, stack: _AppAndClient, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        client = stack.client
        fixtures = await _seed_full_fixture_set(client, admin_engine_lpg_test)
        admin_headers = {"Authorization": f"Bearer {fixtures.admin_token}"}

        # 1. Plan -> 201, planned.
        plan_response = await client.post(
            "/api/v1/routes",
            json={
                "branch_id": str(fixtures.branch_id),
                "driver_id": str(fixtures.driver_id),
                "vehicle_id": str(fixtures.vehicle_id),
            },
            headers=admin_headers,
        )
        assert plan_response.status_code == 201, plan_response.text
        route = plan_response.json()
        route_id = route["id"]
        assert route["status"] == "planned"
        assert route["stops"] == []

        # 2. List -> contains the planned route.
        list_response = await client.get("/api/v1/routes", headers=admin_headers)
        assert list_response.status_code == 200, list_response.text
        assert route_id in {r["id"] for r in list_response.json()["items"]}

        # 3. Get -> 200.
        get_response = await client.get(f"/api/v1/routes/{route_id}", headers=admin_headers)
        assert get_response.status_code == 200, get_response.text
        assert get_response.json()["id"] == route_id

        # 4. Active-for-driver -> 200 (planned counts as active).
        active_response = await client.get(
            f"/api/v1/routes/active-for-driver/{fixtures.driver_id}", headers=admin_headers
        )
        assert active_response.status_code == 200, active_response.text
        assert active_response.json()["id"] == route_id

        # 5. Load the vehicle (BR-12) before assigning any order, so the
        # assignment's reservation math has real vehicle stock to work
        # with -> planned -> loaded.
        load_response = await client.post(
            f"/api/v1/routes/{route_id}/load",
            json={
                "warehouse_id": str(fixtures.warehouse_id),
                "lines": [{"cylinder_type_id": str(fixtures.cylinder_type_id), "quantity": 10}],
            },
            headers=admin_headers,
        )
        assert load_response.status_code == 200, load_response.text
        assert load_response.json()["status"] == "loaded"

        # 6. Assign an unassigned, confirmed order onto this route -> one stop.
        order = await _create_and_confirm_order(client, fixtures, admin_headers, quantity=2)
        assign_response = await client.post(
            f"/api/v1/routes/{route_id}/assign-order",
            json={"order_id": order["id"]},
            headers=admin_headers,
        )
        assert assign_response.status_code == 200, assign_response.text
        assigned_route = assign_response.json()
        assert len(assigned_route["stops"]) == 1
        assert assigned_route["stops"][0]["order_id"] == order["id"]
        assert assigned_route["stops"][0]["status"] == "pending"

        # 7. Dispatch + depart the order -> DepartOrderUseCase advances the
        # route "loaded" -> "in_progress" automatically.
        dispatch_response = await client.post(
            f"/api/v1/orders/{order['id']}/dispatch", headers=admin_headers
        )
        assert dispatch_response.status_code == 200, dispatch_response.text
        depart_response = await client.post(
            f"/api/v1/orders/{order['id']}/depart", headers=admin_headers
        )
        assert depart_response.status_code == 200, depart_response.text
        route_after_depart = (
            await client.get(f"/api/v1/routes/{route_id}", headers=admin_headers)
        ).json()
        assert route_after_depart["status"] == "in_progress"
        otp_code = stack.otp_delivery.sent[-1][1]

        # 8. Attempting reconciliation before any approved reconciliation
        # record exists -> 409 ROUTE_RECONCILIATION_PENDING (route isn't
        # even "completed" yet at this point, which alone would 409 the
        # same way — this exercises the endpoint's own error path).
        premature_reconcile_response = await client.post(
            f"/api/v1/routes/{route_id}/reconcile", headers=admin_headers
        )
        assert premature_reconcile_response.status_code == 409, premature_reconcile_response.text
        assert premature_reconcile_response.json()["error_code"] == "ROUTE_RECONCILIATION_PENDING"

        # 9. Deliver the order's only stop -> Route.record_proof_of_delivery
        # marks the stop delivered and, since it was the route's last
        # unresolved stop, auto-completes the route.
        driver_headers = {"Authorization": f"Bearer {fixtures.driver_token}"}
        deliver_response = await client.post(
            f"/api/v1/orders/{order['id']}/deliver",
            json={
                "lines": [
                    {
                        "cylinder_type_id": str(fixtures.cylinder_type_id),
                        "quantity_delivered": 2,
                        "quantity_collected_empty": 1,
                    }
                ],
                "otp_code": otp_code,
                "proof_of_delivery": {
                    "signature_blob_ref": "sig-ref",
                    "photo_blob_ref": "photo-ref",
                    "gps_lat": "12.9716",
                    "gps_lng": "77.5946",
                    "payment_method": "cash",
                    "amount_collected": "1900.00",
                },
            },
            headers={**driver_headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert deliver_response.status_code == 200, deliver_response.text
        route_after_deliver = (
            await client.get(f"/api/v1/routes/{route_id}", headers=admin_headers)
        ).json()
        assert route_after_deliver["status"] == "completed"
        assert route_after_deliver["stops"][0]["status"] == "delivered"
        assert route_after_deliver["stops"][0]["proof_of_delivery"]["otp_verified"] is True

        # 10. Still pending -> 409, now purely because no reconciliation
        # record has been approved yet (route status is no longer the
        # blocker).
        pending_reconcile_response = await client.post(
            f"/api/v1/routes/{route_id}/reconcile", headers=admin_headers
        )
        assert pending_reconcile_response.status_code == 409, pending_reconcile_response.text

        # 11. Create + approve a reconciliation record for the vehicle via
        # Inventory's own endpoints (Route references Inventory's outcome,
        # per `CompleteRouteReconciliationUseCase`'s docstring).
        reconciliation_response = await client.post(
            f"/api/v1/inventory-locations/vehicle/{fixtures.vehicle_id}/reconciliation-records",
            json={
                "cylinder_type_id": str(fixtures.cylinder_type_id),
                "status": "filled",
                "actual_quantity": 8,
            },
            headers=admin_headers,
        )
        assert reconciliation_response.status_code == 201, reconciliation_response.text
        record_id = reconciliation_response.json()["id"]
        approve_response = await client.post(
            f"/api/v1/reconciliation-records/{record_id}/approve", headers=admin_headers
        )
        assert approve_response.status_code == 200, approve_response.text

        # 12. Reconcile -> 200, reconciled.
        reconcile_response = await client.post(
            f"/api/v1/routes/{route_id}/reconcile", headers=admin_headers
        )
        assert reconcile_response.status_code == 200, reconcile_response.text
        assert reconcile_response.json()["status"] == "reconciled"

        # 13. PATCH .../status directly, on two fresh routes that never go
        # through the order pipeline: "loaded -> in_progress" and
        # "planned -> cancelled".
        second_plan_response = await client.post(
            "/api/v1/routes",
            json={
                "branch_id": str(fixtures.branch_id),
                "driver_id": str(fixtures.driver_id),
                "vehicle_id": str(fixtures.vehicle_id),
            },
            headers=admin_headers,
        )
        assert second_plan_response.status_code == 201, second_plan_response.text
        second_route_id = second_plan_response.json()["id"]
        second_load_response = await client.post(
            f"/api/v1/routes/{second_route_id}/load",
            json={
                "warehouse_id": str(fixtures.warehouse_id),
                "lines": [{"cylinder_type_id": str(fixtures.cylinder_type_id), "quantity": 1}],
            },
            headers=admin_headers,
        )
        assert second_load_response.status_code == 200, second_load_response.text
        status_response = await client.patch(
            f"/api/v1/routes/{second_route_id}/status",
            json={"status": "in_progress"},
            headers=admin_headers,
        )
        assert status_response.status_code == 200, status_response.text
        assert status_response.json()["status"] == "in_progress"

        third_plan_response = await client.post(
            "/api/v1/routes",
            json={
                "branch_id": str(fixtures.branch_id),
                "driver_id": str(fixtures.driver_id),
                "vehicle_id": str(fixtures.vehicle_id),
            },
            headers=admin_headers,
        )
        assert third_plan_response.status_code == 201, third_plan_response.text
        third_route_id = third_plan_response.json()["id"]
        cancel_status_response = await client.patch(
            f"/api/v1/routes/{third_route_id}/status",
            json={"status": "cancelled"},
            headers=admin_headers,
        )
        assert cancel_status_response.status_code == 200, cancel_status_response.text
        assert cancel_status_response.json()["status"] == "cancelled"

        # 14. Illegal transition (cancelled -> in_progress) -> 409.
        illegal_response = await client.patch(
            f"/api/v1/routes/{third_route_id}/status",
            json={"status": "in_progress"},
            headers=admin_headers,
        )
        assert illegal_response.status_code == 409, illegal_response.text
