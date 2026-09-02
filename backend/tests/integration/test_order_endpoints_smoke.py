"""Order Management endpoint smoke tests through the real ASGI stack.

Covers the plan's live-browser verification steps at the API level: full
lifecycle (create -> confirm -> assign -> dispatch -> depart -> deliver ->
close), failed-delivery -> reschedule -> deliver, free cancellation,
post-dispatch cancel -> approve, an illegal transition, role-scoped
`orders:read`, and cross-tenant isolation.
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

    # This suite seeds many synthetic users per test and logs each of them
    # in — a much higher login volume than `auth:login`'s 10/60s rate limit
    # (keyed by client IP, shared across every test in this module since
    # they all originate from the same ASGITransport "127.0.0.1") is sized
    # for. Flushing isolates each test's rate-limit counters the same way
    # every other resource here is already isolated (fresh tenant/UUIDs).
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
    engine: AsyncEngine, *, name: str = "Order Smoke Tenant"
) -> tuple[uuid.UUID, uuid.UUID]:
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), :name, :slug, 'ops@example.com') RETURNING id"
                ),
                {"name": name, "slug": f"order-smoke-{uuid.uuid4().hex[:10]}"},
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


async def _seed_employee(
    engine: AsyncEngine, *, tenant_id: uuid.UUID, branch_id: uuid.UUID
) -> uuid.UUID:
    async with engine.begin() as conn:
        employee_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.employee "
                    "(id, tenant_id, branch_id, employee_code, first_name, last_name, "
                    "phone_number, role, status) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :employee_code, "
                    "'Test', 'Driver', '1234567890', 'driver', 'active') RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id),
                    "employee_code": f"DRV-{uuid.uuid4().hex[:6]}",
                },
            )
        ).scalar_one()
    return uuid.UUID(str(employee_id))


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
        user_id = (
            await conn.execute(
                text(
                    "INSERT INTO identity.identity_user "
                    "(id, tenant_id, branch_id, email, password_hash, role) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :email, "
                    ":password_hash, :role) "
                    "RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id) if branch_id else None,
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


async def _seed_customer(
    engine: AsyncEngine,
    *,
    tenant_id: uuid.UUID,
    branch_id: uuid.UUID,
    email: str,
    password_hash: str,
) -> tuple[uuid.UUID, uuid.UUID]:
    async with engine.begin() as conn:
        _employee_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.employee "
                    "(id, tenant_id, branch_id, employee_code, first_name, last_name, "
                    "phone_number, role, status) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :employee_code, "
                    "'Test', 'Driver', '1234567890', 'driver', 'active') RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id),
                    "employee_code": f"DRV-{uuid.uuid4().hex[:6]}",
                },
            )
        ).scalar_one()
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
        await conn.execute(
            text(
                "INSERT INTO identity.identity_user_permission "
                "(id, user_id, permission_id, created_at) "
                "SELECT gen_random_uuid(), :user_id, rp.permission_id, now() "
                "FROM identity.role_permission rp "
                "JOIN identity.role r ON r.id = rp.role_id "
                "WHERE r.code = :role"
            ),
            {"user_id": identity_user_id, "role": "customer"},
        )
        customer_id = (
            await conn.execute(
                text(
                    "INSERT INTO customer.customer "
                    "(id, tenant_id, branch_id, identity_user_id, customer_type, full_name, "
                    "phone_number, consumer_number) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :identity_user_id, "
                    "'domestic', 'Order Smoke Customer', :phone, :consumer_number) RETURNING id"
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
                    "(id, tenant_id, customer_id, line_1) "
                    "VALUES (gen_random_uuid(), :tenant_id, :customer_id, '123 Test St') "
                    "RETURNING id"
                ),
                {"tenant_id": str(tenant_id), "customer_id": str(customer_id)},
            )
        ).scalar_one()
    return uuid.UUID(str(customer_id)), uuid.UUID(str(address_id))


async def _seed_driver(
    engine: AsyncEngine,
    *,
    tenant_id: uuid.UUID,
    branch_id: uuid.UUID,
    email: str,
    password_hash: str,
) -> uuid.UUID:
    async with engine.begin() as conn:
        employee_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.employee "
                    "(id, tenant_id, branch_id, employee_code, first_name, last_name, "
                    "phone_number, role, status) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :employee_code, "
                    "'Test', 'Driver', '1234567890', 'driver', 'active') RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id),
                    "employee_code": f"DRV-{uuid.uuid4().hex[:6]}",
                },
            )
        ).scalar_one()
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
        await conn.execute(
            text(
                "INSERT INTO identity.identity_user_permission "
                "(id, user_id, permission_id, created_at) "
                "SELECT gen_random_uuid(), :user_id, rp.permission_id, now() "
                "FROM identity.role_permission rp "
                "JOIN identity.role r ON r.id = rp.role_id "
                "WHERE r.code = :role"
            ),
            {"user_id": identity_user_id, "role": "driver"},
        )
        driver_id = (
            await conn.execute(
                text(
                    "INSERT INTO delivery.driver "
                    "(id, tenant_id, branch_id, identity_user_id, employee_id, license_number) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :identity_user_id, "
                    ":employee_id, 'DL123456') RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id),
                    "identity_user_id": str(identity_user_id),
                    "employee_id": str(employee_id),
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
    """Stock a warehouse's `filled` balance — needed so `POST /routes/{id}/
    load` (BR-12) has something to transfer onto the vehicle before a route
    can move `planned -> loaded`, a precondition `DepartOrderUseCase`/
    `Route.record_proof_of_delivery()`/`.record_failed_delivery()` now
    enforce (Phase 12) that this suite's order-lifecycle flows must satisfy
    before they can depart/deliver/fail-deliver.
    """
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


async def _route_id_for_driver(engine: AsyncEngine, *, driver_id: uuid.UUID) -> str:
    """The most-recently-planned route for this driver — `AssignOrderUseCase`'s
    find-or-create path (`application/order/use_cases.py`) plans exactly one
    route per driver/vehicle/day the first time an order is assigned to
    them, so this is unambiguous within a single test.
    """
    async with engine.begin() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT id FROM delivery.route WHERE driver_id = :driver_id "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"driver_id": str(driver_id)},
            )
        ).first()
        assert row is not None, f"No route planned for driver {driver_id}."
        return str(row[0])


async def _load_route(
    client: AsyncClient,
    *,
    route_id: str,
    warehouse_id: uuid.UUID,
    cylinder_type_id: uuid.UUID,
    quantity: int,
    headers: dict[str, str],
) -> None:
    """`planned -> loaded` (BR-12) — required before a route's first order
    can depart and, in turn, before that order can be delivered or marked a
    failed delivery (`Route.record_proof_of_delivery`/`.record_failed_
    delivery` both require `in_progress`, which `DepartOrderUseCase` only
    reaches from `loaded`).
    """
    response = await client.post(
        f"/api/v1/routes/{route_id}/load",
        json={
            "warehouse_id": str(warehouse_id),
            "lines": [{"cylinder_type_id": str(cylinder_type_id), "quantity": quantity}],
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text


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


async def _seed_cancellation_fee(
    engine: AsyncEngine, *, tenant_id: uuid.UUID, policy_type: str, amount: str
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO tenant.tenant_configuration "
                "(id, tenant_id, config_key, config_value, effective_from) "
                "VALUES (gen_random_uuid(), :tenant_id, 'cancellation_fee_amount', "
                "CAST(:config_value AS jsonb), :effective_from)"
            ),
            {
                "tenant_id": str(tenant_id),
                "config_value": f'{{"policy_type": "{policy_type}", "amount": "{amount}"}}',
                "effective_from": datetime.now(UTC) - timedelta(days=1),
            },
        )


async def _seed_vehicle_stock(
    engine: AsyncEngine,
    *,
    tenant_id: uuid.UUID,
    vehicle_id: uuid.UUID,
    cylinder_type_id: uuid.UUID,
    quantity: int,
) -> None:
    async with engine.begin() as conn:
        location_id = (
            await conn.execute(
                text(
                    "INSERT INTO inventory.inventory_location "
                    "(id, tenant_id, location_type, location_ref_id) "
                    "VALUES (gen_random_uuid(), :tenant_id, 'vehicle', :vehicle_id) RETURNING id"
                ),
                {"tenant_id": str(tenant_id), "vehicle_id": str(vehicle_id)},
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


async def _vehicle_filled_balance(
    engine: AsyncEngine, *, vehicle_id: uuid.UUID, cylinder_type_id: uuid.UUID
) -> int:
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                "SELECT ib.quantity FROM inventory.inventory_balance ib "
                "JOIN inventory.inventory_location il ON il.id = ib.inventory_location_id "
                "WHERE il.location_ref_id = :vehicle_id "
                "AND ib.cylinder_type_id = :cylinder_type_id AND ib.status = 'filled'"
            ),
            {"vehicle_id": str(vehicle_id), "cylinder_type_id": str(cylinder_type_id)},
        )
        row = result.first()
        return int(row[0]) if row is not None else 0


async def _login(client: AsyncClient, *, email: str, password: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    access_token: str = response.json()["access_token"]
    return access_token


@dataclass
class _Fixtures:
    tenant_id: uuid.UUID
    branch_id: uuid.UUID
    admin_token: str
    customer_id: uuid.UUID
    customer_token: str
    address_id: uuid.UUID
    driver_id: uuid.UUID
    driver_token: str
    driver_email: str
    driver_password: str
    vehicle_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    warehouse_id: uuid.UUID


async def _seed_full_fixture_set(
    client: AsyncClient, engine: AsyncEngine, *, unit_price: Decimal = Decimal("950.00")
) -> _Fixtures:
    hasher = Argon2PasswordHasher(_settings_for_hasher())
    tenant_id, branch_id = await _seed_tenant_and_branch(engine)

    admin_email = f"{uuid.uuid4().hex}@order-smoke.example"
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

    customer_email = f"{uuid.uuid4().hex}@order-smoke.example"
    customer_password = "correct horse battery staple 43"
    customer_id, address_id = await _seed_customer(
        engine,
        tenant_id=tenant_id,
        branch_id=branch_id,
        email=customer_email,
        password_hash=hasher.hash(customer_password),
    )
    customer_token = await _login(client, email=customer_email, password=customer_password)

    driver_email = f"{uuid.uuid4().hex}@order-smoke.example"
    driver_password = "correct horse battery staple 44"
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
    await _seed_price_list(
        engine, tenant_id=tenant_id, cylinder_type_id=cylinder_type_id, price=unit_price
    )
    await _seed_vehicle_stock(
        engine,
        tenant_id=tenant_id,
        vehicle_id=vehicle_id,
        cylinder_type_id=cylinder_type_id,
        quantity=100,
    )
    warehouse_id = await _seed_warehouse(engine, tenant_id=tenant_id, branch_id=branch_id)
    await _seed_warehouse_stock(
        engine,
        tenant_id=tenant_id,
        warehouse_id=warehouse_id,
        cylinder_type_id=cylinder_type_id,
        quantity=100,
    )

    return _Fixtures(
        tenant_id=tenant_id,
        branch_id=branch_id,
        admin_token=admin_token,
        customer_id=customer_id,
        customer_token=customer_token,
        address_id=address_id,
        driver_id=driver_id,
        driver_token=driver_token,
        driver_email=driver_email,
        driver_password=driver_password,
        vehicle_id=vehicle_id,
        cylinder_type_id=cylinder_type_id,
        warehouse_id=warehouse_id,
    )


def _settings_for_hasher() -> Settings:
    from lpg.config.settings import Settings

    return Settings(environment="local", log_json=False)


def _create_order_payload(fixtures: _Fixtures, *, quantity: int = 2) -> dict[str, Any]:
    return {
        "branch_id": str(fixtures.branch_id),
        "customer_id": str(fixtures.customer_id),
        "address_id": str(fixtures.address_id),
        "delivery_address": {
            "address_line": "123 Test St",
            "latitude": 12.9716,
            "longitude": 77.5946,
        },
        "booking_source": "staff",
        "requested_date": datetime.now(UTC).isoformat(),
        "lines": [{"cylinder_type_id": str(fixtures.cylinder_type_id), "quantity": quantity}],
    }


async def _create_order(
    client: AsyncClient, fixtures: _Fixtures, headers: dict[str, str], *, quantity: int = 2
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/orders",
        json=_create_order_payload(fixtures, quantity=quantity),
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


# ==========================================================================
# Full lifecycle
# ==========================================================================


class TestOrderFullLifecycle:
    async def test_create_confirm_assign_dispatch_depart_deliver_close(
        self, stack: _AppAndClient, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        client = stack.client
        fixtures = await _seed_full_fixture_set(client, admin_engine_lpg_test)
        admin_headers = {"Authorization": f"Bearer {fixtures.admin_token}"}

        # 1. Create -> 201, booked.
        idempotency_key = str(uuid.uuid4())
        create_payload = _create_order_payload(fixtures)
        create_response = await client.post(
            "/api/v1/orders",
            json=create_payload,
            headers={**admin_headers, "Idempotency-Key": idempotency_key},
        )
        assert create_response.status_code == 201, create_response.text
        order = create_response.json()
        assert order["status"] == "booked"
        order_id = order["id"]

        # 1b. Idempotency-Key replay — same body (byte-for-byte, including
        # `requested_date`), same key -> same order id, no second order
        # created.
        replay_response = await client.post(
            "/api/v1/orders",
            json=create_payload,
            headers={**admin_headers, "Idempotency-Key": idempotency_key},
        )
        assert replay_response.status_code == 201, replay_response.text
        assert replay_response.json()["id"] == order_id

        # 2. Confirm -> total_amount populated.
        confirm_response = await client.post(
            f"/api/v1/orders/{order_id}/confirm", headers=admin_headers
        )
        assert confirm_response.status_code == 200, confirm_response.text
        confirmed = confirm_response.json()
        assert confirmed["status"] == "confirmed"
        assert Decimal(confirmed["total_amount"]) == Decimal("1900.00")
        assert Decimal(confirmed["lines"][0]["unit_price"]) == Decimal("950.00")

        # 3. Assign -> assigned; vehicle balance drops by 2.
        assign_response = await client.post(
            f"/api/v1/orders/{order_id}/assign",
            json={"driver_id": str(fixtures.driver_id), "vehicle_id": str(fixtures.vehicle_id)},
            headers=admin_headers,
        )
        assert assign_response.status_code == 200, assign_response.text
        assert assign_response.json()["status"] == "assigned"
        balance_after_assign = await _vehicle_filled_balance(
            admin_engine_lpg_test,
            vehicle_id=fixtures.vehicle_id,
            cylinder_type_id=fixtures.cylinder_type_id,
        )
        assert balance_after_assign == 98

        # 3b. Load the route's vehicle (BR-12) — required before this order's
        # route can reach "in_progress" (Phase 12: `Route.record_proof_of_
        # delivery`/`.record_failed_delivery` both require it, and
        # `DepartOrderUseCase` only advances a route from "loaded").
        route_id = await _route_id_for_driver(admin_engine_lpg_test, driver_id=fixtures.driver_id)
        await _load_route(
            client,
            route_id=route_id,
            warehouse_id=fixtures.warehouse_id,
            cylinder_type_id=fixtures.cylinder_type_id,
            quantity=1,
            headers=admin_headers,
        )
        balance_after_load = await _vehicle_filled_balance(
            admin_engine_lpg_test,
            vehicle_id=fixtures.vehicle_id,
            cylinder_type_id=fixtures.cylinder_type_id,
        )
        assert balance_after_load == 99

        # 4. Dispatch -> ready_for_dispatch.
        dispatch_response = await client.post(
            f"/api/v1/orders/{order_id}/dispatch", headers=admin_headers
        )
        assert dispatch_response.status_code == 200, dispatch_response.text
        assert dispatch_response.json()["status"] == "ready_for_dispatch"

        driver_headers = {"Authorization": f"Bearer {fixtures.driver_token}"}

        # 4b. A *different* driver cannot depart this order — the `orders:dispatch`
        # grant is shared, but the ownership guard 404s (never 403) on a stop
        # that belongs to someone else's route.
        hasher = Argon2PasswordHasher(_settings_for_hasher())
        other_driver_email = f"{uuid.uuid4().hex}@order-smoke.example"
        other_driver_password = "correct horse battery staple 45"
        await _seed_driver(
            admin_engine_lpg_test,
            tenant_id=fixtures.tenant_id,
            branch_id=fixtures.branch_id,
            email=other_driver_email,
            password_hash=hasher.hash(other_driver_password),
        )
        other_driver_token = await _login(
            client, email=other_driver_email, password=other_driver_password
        )
        not_yours_response = await client.post(
            f"/api/v1/orders/{order_id}/depart",
            headers={"Authorization": f"Bearer {other_driver_token}"},
        )
        assert not_yours_response.status_code == 404, not_yours_response.text
        assert len(stack.otp_delivery.sent) == 0

        # 5. The assigned driver departs their own order -> out_for_delivery;
        # OTP captured via the dependency override.
        depart_key = str(uuid.uuid4())
        depart_response = await client.post(
            f"/api/v1/orders/{order_id}/depart",
            headers={**driver_headers, "Idempotency-Key": depart_key},
        )
        assert depart_response.status_code == 200, depart_response.text
        assert depart_response.json()["status"] == "out_for_delivery"
        assert len(stack.otp_delivery.sent) == 1
        otp_code = stack.otp_delivery.sent[-1][1]

        # 5b. Idempotency replay (the offline Driver App re-sends a queued
        # depart after a dropped connection): same key -> the stored result,
        # and crucially the use case does NOT run again, so no second OTP.
        depart_replay = await client.post(
            f"/api/v1/orders/{order_id}/depart",
            headers={**driver_headers, "Idempotency-Key": depart_key},
        )
        assert depart_replay.status_code == 200, depart_replay.text
        assert depart_replay.json()["status"] == "out_for_delivery"
        assert len(stack.otp_delivery.sent) == 1

        # 6. Driver's own scoped queue shows this order.
        driver_list_response = await client.get("/api/v1/orders", headers=driver_headers)
        assert driver_list_response.status_code == 200, driver_list_response.text
        driver_orders = driver_list_response.json()
        assert any(o["id"] == order_id for o in driver_orders["items"])

        # 7. Pre-upload a POD attachment, then deliver in full (cash payment).
        upload_response = await client.post(
            f"/api/v1/orders/{order_id}/pod-attachments",
            files={"file": ("signature.png", b"fake-png-bytes", "image/png")},
            headers=driver_headers,
        )
        assert upload_response.status_code == 201, upload_response.text
        blob_ref = upload_response.json()["blob_ref"]

        deliver_idempotency_key = str(uuid.uuid4())
        deliver_response = await client.post(
            f"/api/v1/orders/{order_id}/deliver",
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
                    "signature_blob_ref": blob_ref,
                    "photo_blob_ref": blob_ref,
                    "gps_lat": "12.9716",
                    "gps_lng": "77.5946",
                    "payment_method": "cash",
                    "amount_collected": "1900.00",
                },
            },
            headers={**driver_headers, "Idempotency-Key": deliver_idempotency_key},
        )
        assert deliver_response.status_code == 200, deliver_response.text
        deliver_body = deliver_response.json()
        assert deliver_body["order"]["status"] == "delivered"
        assert "invoice_id" not in deliver_body
        assert "ledger_transaction_id" not in deliver_body
        assert "invoice_id" not in deliver_body["order"]

        # Reserve-then-deliver-in-full must not double-count: balance is
        # unchanged since step 3b's load (99), only the +1 collected empty
        # is new — filled stays 99.
        balance_after_deliver = await _vehicle_filled_balance(
            admin_engine_lpg_test,
            vehicle_id=fixtures.vehicle_id,
            cylinder_type_id=fixtures.cylinder_type_id,
        )
        assert balance_after_deliver == 99

        # 8. Close -> closed.
        close_response = await client.post(
            f"/api/v1/orders/{order_id}/close", headers=admin_headers
        )
        assert close_response.status_code == 200, close_response.text
        assert close_response.json()["status"] == "closed"

        # 9. order_status_history has 7 rows: booked, confirmed, assigned,
        # ready_for_dispatch, out_for_delivery, delivered, closed.
        async with admin_engine_lpg_test.begin() as conn:
            history_count = (
                await conn.execute(
                    text("SELECT COUNT(*) FROM orders.order_status_history WHERE order_id = :oid"),
                    {"oid": order_id},
                )
            ).scalar_one()
            assert history_count == 7

            pod_count = (
                await conn.execute(
                    text("SELECT COUNT(*) FROM orders.proof_of_delivery WHERE order_id = :oid"),
                    {"oid": order_id},
                )
            ).scalar_one()
            assert pod_count == 1

        # 10. Illegal transition (already closed -> close again) -> 409.
        illegal_response = await client.post(
            f"/api/v1/orders/{order_id}/close", headers=admin_headers
        )
        assert illegal_response.status_code == 409, illegal_response.text
        assert illegal_response.json()["error_code"] == "INVALID_STATE_TRANSITION"


# ==========================================================================
# Failed delivery -> reschedule -> deliver
# ==========================================================================


class TestFailedDeliveryAndReschedule:
    async def test_failed_delivery_then_reschedule_then_deliver(
        self, stack: _AppAndClient, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        client = stack.client
        fixtures = await _seed_full_fixture_set(client, admin_engine_lpg_test)
        admin_headers = {"Authorization": f"Bearer {fixtures.admin_token}"}
        driver_headers = {"Authorization": f"Bearer {fixtures.driver_token}"}

        order = await _create_order(client, fixtures, admin_headers, quantity=1)
        order_id = order["id"]
        await client.post(f"/api/v1/orders/{order_id}/confirm", headers=admin_headers)
        await client.post(
            f"/api/v1/orders/{order_id}/assign",
            json={"driver_id": str(fixtures.driver_id), "vehicle_id": str(fixtures.vehicle_id)},
            headers=admin_headers,
        )
        route_id = await _route_id_for_driver(admin_engine_lpg_test, driver_id=fixtures.driver_id)
        await _load_route(
            client,
            route_id=route_id,
            warehouse_id=fixtures.warehouse_id,
            cylinder_type_id=fixtures.cylinder_type_id,
            quantity=1,
            headers=admin_headers,
        )
        dispatch_response = await client.post(
            f"/api/v1/orders/{order_id}/dispatch", headers=admin_headers
        )
        assert dispatch_response.status_code == 200, dispatch_response.text
        first_depart_response = await client.post(
            f"/api/v1/orders/{order_id}/depart", headers=admin_headers
        )
        assert first_depart_response.status_code == 200, first_depart_response.text

        failed_key = str(uuid.uuid4())
        failed_body = {
            "reason_code": "customer_unavailable",
            "resolution_action": "reschedule",
        }
        failed_response = await client.post(
            f"/api/v1/orders/{order_id}/failed-delivery",
            json=failed_body,
            headers={**driver_headers, "Idempotency-Key": failed_key},
        )
        assert failed_response.status_code == 200, failed_response.text
        assert failed_response.json()["status"] == "failed_delivery"

        # Replay (same key, same body) -> stored result, no re-transition.
        failed_replay = await client.post(
            f"/api/v1/orders/{order_id}/failed-delivery",
            json=failed_body,
            headers={**driver_headers, "Idempotency-Key": failed_key},
        )
        assert failed_replay.status_code == 200, failed_replay.text
        assert failed_replay.json()["status"] == "failed_delivery"

        # Same key, *different* body -> 409, never silently a new transition.
        failed_conflict = await client.post(
            f"/api/v1/orders/{order_id}/failed-delivery",
            json={"reason_code": "wrong_address", "resolution_action": "reschedule"},
            headers={**driver_headers, "Idempotency-Key": failed_key},
        )
        assert failed_conflict.status_code == 409, failed_conflict.text

        reschedule_key = str(uuid.uuid4())
        reschedule_response = await client.post(
            f"/api/v1/orders/{order_id}/reschedule",
            headers={**admin_headers, "Idempotency-Key": reschedule_key},
        )
        assert reschedule_response.status_code == 200, reschedule_response.text
        assert reschedule_response.json()["status"] == "ready_for_dispatch"

        reschedule_replay = await client.post(
            f"/api/v1/orders/{order_id}/reschedule",
            headers={**admin_headers, "Idempotency-Key": reschedule_key},
        )
        assert reschedule_replay.status_code == 200, reschedule_replay.text
        assert reschedule_replay.json()["status"] == "ready_for_dispatch"

        # Depart again to get a fresh OTP, then deliver.
        stack.otp_delivery.sent.clear()
        second_depart_response = await client.post(
            f"/api/v1/orders/{order_id}/depart", headers=admin_headers
        )
        assert second_depart_response.status_code == 200, second_depart_response.text
        otp_code = stack.otp_delivery.sent[-1][1]

        deliver_response = await client.post(
            f"/api/v1/orders/{order_id}/deliver",
            json={
                "lines": [
                    {
                        "cylinder_type_id": str(fixtures.cylinder_type_id),
                        "quantity_delivered": 1,
                        "quantity_collected_empty": 0,
                    }
                ],
                "otp_code": otp_code,
                "proof_of_delivery": {
                    "signature_blob_ref": "sig-ref",
                    "photo_blob_ref": "photo-ref",
                    "gps_lat": "12.9716",
                    "gps_lng": "77.5946",
                    "payment_method": "cash",
                    "amount_collected": "0",
                },
            },
            headers={**driver_headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert deliver_response.status_code == 200, deliver_response.text
        assert deliver_response.json()["order"]["status"] == "delivered"


# ==========================================================================
# Cancellation — free path
# ==========================================================================


class TestFreeCancellation:
    async def test_free_cancel_from_assigned_restores_vehicle_balance(
        self, stack: _AppAndClient, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        client = stack.client
        fixtures = await _seed_full_fixture_set(client, admin_engine_lpg_test)
        admin_headers = {"Authorization": f"Bearer {fixtures.admin_token}"}

        order = await _create_order(client, fixtures, admin_headers, quantity=3)
        order_id = order["id"]
        await client.post(f"/api/v1/orders/{order_id}/confirm", headers=admin_headers)
        await client.post(
            f"/api/v1/orders/{order_id}/assign",
            json={"driver_id": str(fixtures.driver_id), "vehicle_id": str(fixtures.vehicle_id)},
            headers=admin_headers,
        )
        balance_after_assign = await _vehicle_filled_balance(
            admin_engine_lpg_test,
            vehicle_id=fixtures.vehicle_id,
            cylinder_type_id=fixtures.cylinder_type_id,
        )
        assert balance_after_assign == 97

        cancel_response = await client.post(
            f"/api/v1/orders/{order_id}/cancel",
            json={"reason": "Customer changed their mind"},
            headers=admin_headers,
        )
        assert cancel_response.status_code == 200, cancel_response.text
        cancel_body = cancel_response.json()
        assert cancel_body["pending_approval"] is False
        assert cancel_body["order"]["status"] == "cancelled"

        balance_after_cancel = await _vehicle_filled_balance(
            admin_engine_lpg_test,
            vehicle_id=fixtures.vehicle_id,
            cylinder_type_id=fixtures.cylinder_type_id,
        )
        assert balance_after_cancel == 100


# ==========================================================================
# Cancellation — post-dispatch approval path
# ==========================================================================


class TestPostDispatchCancellationApproval:
    async def test_cancel_then_approve_charges_the_seeded_flat_fee(
        self, stack: _AppAndClient, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        client = stack.client
        fixtures = await _seed_full_fixture_set(client, admin_engine_lpg_test)
        await _seed_cancellation_fee(
            admin_engine_lpg_test, tenant_id=fixtures.tenant_id, policy_type="flat", amount="150.00"
        )
        admin_headers = {"Authorization": f"Bearer {fixtures.admin_token}"}

        order = await _create_order(client, fixtures, admin_headers, quantity=2)
        order_id = order["id"]
        await client.post(f"/api/v1/orders/{order_id}/confirm", headers=admin_headers)
        await client.post(
            f"/api/v1/orders/{order_id}/assign",
            json={"driver_id": str(fixtures.driver_id), "vehicle_id": str(fixtures.vehicle_id)},
            headers=admin_headers,
        )
        await client.post(f"/api/v1/orders/{order_id}/dispatch", headers=admin_headers)
        await client.post(f"/api/v1/orders/{order_id}/depart", headers=admin_headers)

        cancel_response = await client.post(
            f"/api/v1/orders/{order_id}/cancel",
            json={"reason": "Vehicle breakdown"},
            headers=admin_headers,
        )
        assert cancel_response.status_code == 202, cancel_response.text
        assert cancel_response.json()["pending_approval"] is True
        assert cancel_response.json()["order"]["status"] == "out_for_delivery"

        approve_response = await client.post(
            f"/api/v1/orders/{order_id}/cancel/approve", headers=admin_headers
        )
        assert approve_response.status_code == 200, approve_response.text
        assert approve_response.json()["status"] == "cancelled"

        async with admin_engine_lpg_test.begin() as conn:
            charge = (
                await conn.execute(
                    text(
                        "SELECT cancellation_charge FROM orders.cancellation_record "
                        "WHERE order_id = :oid"
                    ),
                    {"oid": order_id},
                )
            ).scalar_one()
            assert Decimal(charge) == Decimal("150.00")

        balance_after_approve = await _vehicle_filled_balance(
            admin_engine_lpg_test,
            vehicle_id=fixtures.vehicle_id,
            cylinder_type_id=fixtures.cylinder_type_id,
        )
        assert balance_after_approve == 100


# ==========================================================================
# Bulk cancel (synchronous path, <= threshold)
# ==========================================================================


class TestBulkCancelSynchronous:
    async def test_bulk_cancel_two_orders_synchronously(
        self, stack: _AppAndClient, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        client = stack.client
        fixtures = await _seed_full_fixture_set(client, admin_engine_lpg_test)
        admin_headers = {"Authorization": f"Bearer {fixtures.admin_token}"}

        order_a = await _create_order(client, fixtures, admin_headers, quantity=1)
        order_b = await _create_order(client, fixtures, admin_headers, quantity=1)

        response = await client.post(
            "/api/v1/orders/bulk-cancel",
            json={
                "order_ids": [order_a["id"], order_b["id"]],
                "reason": "Bulk test cancellation",
            },
            headers=admin_headers,
        )
        assert response.status_code == 202, response.text
        body = response.json()
        assert body["job_id"] is None
        assert body["results"] is not None
        assert {r["order_id"] for r in body["results"]} == {order_a["id"], order_b["id"]}
        assert all(r["succeeded"] for r in body["results"]), body["results"]


# ==========================================================================
# Role-scoping
# ==========================================================================


class TestRoleScopedReads:
    async def test_customer_sees_only_their_own_order(
        self, stack: _AppAndClient, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        client = stack.client
        fixtures = await _seed_full_fixture_set(client, admin_engine_lpg_test)
        admin_headers = {"Authorization": f"Bearer {fixtures.admin_token}"}
        customer_headers = {"Authorization": f"Bearer {fixtures.customer_token}"}

        # This customer's own order.
        own_order = await _create_order(client, fixtures, admin_headers)

        # A second, unrelated customer's order in the same tenant/branch.
        hasher = Argon2PasswordHasher(_settings_for_hasher())
        other_email = f"{uuid.uuid4().hex}@order-smoke.example"
        other_password = "correct horse battery staple 45"
        other_customer_id, other_address_id = await _seed_customer(
            admin_engine_lpg_test,
            tenant_id=fixtures.tenant_id,
            branch_id=fixtures.branch_id,
            email=other_email,
            password_hash=hasher.hash(other_password),
        )
        other_order_payload = _create_order_payload(fixtures)
        other_order_payload["customer_id"] = str(other_customer_id)
        other_order_payload["address_id"] = str(other_address_id)
        other_order_response = await client.post(
            "/api/v1/orders",
            json=other_order_payload,
            headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert other_order_response.status_code == 201, other_order_response.text
        other_order_id = other_order_response.json()["id"]

        list_response = await client.get("/api/v1/orders", headers=customer_headers)
        assert list_response.status_code == 200, list_response.text
        order_ids = {o["id"] for o in list_response.json()["items"]}
        assert own_order["id"] in order_ids
        assert other_order_id not in order_ids

        get_other_response = await client.get(
            f"/api/v1/orders/{other_order_id}", headers=customer_headers
        )
        assert get_other_response.status_code == 404, get_other_response.text

    async def test_dispatcher_sees_only_branch_orders(
        self, stack: _AppAndClient, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        client = stack.client
        fixtures = await _seed_full_fixture_set(client, admin_engine_lpg_test)
        admin_headers = {"Authorization": f"Bearer {fixtures.admin_token}"}
        own_branch_order = await _create_order(client, fixtures, admin_headers)

        # A second branch in the *same* tenant with its own order — the
        # dispatcher, scoped to `fixtures.branch_id`, must not see it.
        async with admin_engine_lpg_test.begin() as conn:
            other_branch_id = (
                await conn.execute(
                    text(
                        "INSERT INTO tenant.branch (id, tenant_id, name) "
                        "VALUES (gen_random_uuid(), :tenant_id, 'Other Branch') RETURNING id"
                    ),
                    {"tenant_id": str(fixtures.tenant_id)},
                )
            ).scalar_one()
        other_branch_payload = _create_order_payload(fixtures)
        other_branch_payload["branch_id"] = str(other_branch_id)
        other_branch_response = await client.post(
            "/api/v1/orders",
            json=other_branch_payload,
            headers={**admin_headers, "Idempotency-Key": str(uuid.uuid4())},
        )
        assert other_branch_response.status_code == 201, other_branch_response.text
        other_branch_order_id = other_branch_response.json()["id"]

        hasher = Argon2PasswordHasher(_settings_for_hasher())
        dispatcher_password = "correct horse battery staple 46"
        dispatcher_email = f"{uuid.uuid4().hex}@order-smoke.example"
        await _seed_staff_user(
            admin_engine_lpg_test,
            tenant_id=fixtures.tenant_id,
            branch_id=fixtures.branch_id,
            email=dispatcher_email,
            password_hash=hasher.hash(dispatcher_password),
            role="dispatcher",
        )
        dispatcher_token = await _login(
            client, email=dispatcher_email, password=dispatcher_password
        )
        dispatcher_headers = {"Authorization": f"Bearer {dispatcher_token}"}

        list_response = await client.get("/api/v1/orders", headers=dispatcher_headers)
        assert list_response.status_code == 200, list_response.text
        order_ids = {o["id"] for o in list_response.json()["items"]}
        assert own_branch_order["id"] in order_ids
        assert other_branch_order_id not in order_ids


class TestCrossTenantIsolation:
    async def test_another_tenants_admin_cannot_see_this_order(
        self, stack: _AppAndClient, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        client = stack.client
        fixtures = await _seed_full_fixture_set(client, admin_engine_lpg_test)
        admin_headers = {"Authorization": f"Bearer {fixtures.admin_token}"}
        order = await _create_order(client, fixtures, admin_headers)

        other_tenant_id, other_branch_id = await _seed_tenant_and_branch(
            admin_engine_lpg_test, name="Cross Tenant Isolation Co"
        )
        hasher = Argon2PasswordHasher(_settings_for_hasher())
        other_admin_password = "correct horse battery staple 47"
        other_admin_email = f"{uuid.uuid4().hex}@order-smoke.example"
        await _seed_staff_user(
            admin_engine_lpg_test,
            tenant_id=other_tenant_id,
            branch_id=other_branch_id,
            email=other_admin_email,
            password_hash=hasher.hash(other_admin_password),
            role="agency_admin",
        )
        other_admin_token = await _login(
            client, email=other_admin_email, password=other_admin_password
        )
        other_headers = {"Authorization": f"Bearer {other_admin_token}"}

        get_response = await client.get(f"/api/v1/orders/{order['id']}", headers=other_headers)
        assert get_response.status_code == 404, get_response.text
