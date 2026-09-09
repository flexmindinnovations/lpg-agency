"""Auto-assignment (zero-click driver assignment), through the real ASGI
stack + a real ARQ worker burst run — the trigger (`BookingConfirmed` ->
enqueue), the kill switch, the no-eligible-driver fallback, and the actual
mutation all go through real code, not mocks: a real Postgres session (the
advisory-lock race mitigation is Postgres-specific and cannot be verified
any other way) and a real Redis-backed ARQ queue.

Confirming an order via `POST /orders/{id}/confirm` fires the real
`BookingConfirmed` event through the app's own `DomainEventDispatcher`
(`api/app.py`'s lifespan wiring), which enqueues the real
`auto_assign_driver` ARQ job. A burst-mode `arq.worker.Worker` (same
pattern as `test_job_worker.py`) then actually processes it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send(self, phone_number: str, code: str) -> None:
        self.sent.append((phone_number, code))


@dataclass
class _AppAndClient:
    app: FastAPI
    client: AsyncClient


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

    redis_client = redis_asyncio.from_url(str(integration_settings.redis_url))  # type: ignore[no-untyped-call]
    await redis_client.flushdb()
    await redis_client.aclose()

    from lpg.api.app import create_app
    from lpg.config.settings import get_settings

    get_settings.cache_clear()
    app: FastAPI = create_app(integration_settings)
    app.dependency_overrides[get_otp_delivery] = lambda: _CapturingOtpDelivery()
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
            yield _AppAndClient(app=app, client=http_client)
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
# Seed helpers — self-contained duplicates of `test_route_endpoints_smoke.
# py`'s own, trimmed to what this suite needs (no cross-test-file imports
# anywhere else in this codebase either — same self-containment reasoning
# `tests/integration/conftest.py` already documents for its own helpers).
# ==========================================================================


async def _seed_tenant_and_branch(engine: AsyncEngine) -> tuple[uuid.UUID, uuid.UUID]:
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'Auto-Assign Smoke Tenant', :slug, "
                    "'ops@example.com') RETURNING id"
                ),
                {"slug": f"auto-assign-smoke-{uuid.uuid4().hex[:10]}"},
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
    branch_id: uuid.UUID,
    email: str,
    password_hash: str,
    role: str,
) -> None:
    async with engine.begin() as conn:
        phone_number = f"+91{uuid.uuid4().int % 10**9:09d}"
        user_id = (
            await conn.execute(
                text(
                    "INSERT INTO identity.identity_user "
                    "(id, tenant_id, branch_id, email, phone_number, password_hash, role) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :email, :phone_number, "
                    ":password_hash, :role) RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id),
                    "email": email,
                    "phone_number": phone_number,
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
        # `EmployeeBranchStaffResolver` (used by `delivery_failed_staff`/
        # `order_unassignable_staff`) resolves branch staff via
        # `tenant.employee` -> phone number -> `identity.identity_user`, not
        # directly off the identity role — this row is what makes that join
        # actually find this admin.
        await conn.execute(
            text(
                "INSERT INTO tenant.employee "
                "(id, tenant_id, branch_id, employee_code, first_name, last_name, "
                "phone_number, role, status) "
                "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :employee_code, "
                "'Test', 'Admin', :phone_number, :role, 'active')"
            ),
            {
                "tenant_id": str(tenant_id),
                "branch_id": str(branch_id),
                "employee_code": f"EMP-{uuid.uuid4().hex[:6]}",
                "phone_number": phone_number,
                "role": role,
            },
        )


async def _seed_driver(
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
        driver_id = (
            await conn.execute(
                text(
                    "INSERT INTO delivery.driver "
                    "(id, tenant_id, branch_id, employee_id, license_number, status) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :employee_id, "
                    "'DL123456', 'active') RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id),
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
                    "(id, tenant_id, branch_id, registration_number, make, model, "
                    "capacity_units, status) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :reg, 'Tata', 'Ace', "
                    "50, 'active') RETURNING id"
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


async def _seed_warehouse_with_stock(
    engine: AsyncEngine, *, tenant_id: uuid.UUID, branch_id: uuid.UUID, cylinder_type_id: uuid.UUID
) -> None:
    async with engine.begin() as conn:
        warehouse_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.warehouse (id, tenant_id, branch_id, name, address_line) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, 'Main WH', '1 Depot Rd') "
                    "RETURNING id"
                ),
                {"tenant_id": str(tenant_id), "branch_id": str(branch_id)},
            )
        ).scalar_one()
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
                "'filled', 100)"
            ),
            {
                "tenant_id": str(tenant_id),
                "location_id": str(location_id),
                "cylinder_type_id": str(cylinder_type_id),
            },
        )


async def _seed_customer(
    engine: AsyncEngine, *, tenant_id: uuid.UUID, branch_id: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID]:
    async with engine.begin() as conn:
        customer_id = (
            await conn.execute(
                text(
                    "INSERT INTO customer.customer "
                    "(id, tenant_id, branch_id, customer_type, full_name, phone_number, "
                    "consumer_number) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, 'domestic', "
                    "'Auto-Assign Smoke Customer', :phone, :consumer_number) RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id),
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


async def _seed_price_list(
    engine: AsyncEngine, *, tenant_id: uuid.UUID, cylinder_type_id: uuid.UUID
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO tenant.price_list "
                "(id, tenant_id, cylinder_type_id, customer_type, branch_id, price, "
                "effective_from) "
                "VALUES (gen_random_uuid(), :tenant_id, :cylinder_type_id, 'domestic', NULL, "
                "'950.00', :effective_from)"
            ),
            {
                "tenant_id": str(tenant_id),
                "cylinder_type_id": str(cylinder_type_id),
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
    cylinder_type_id: uuid.UUID
    customer_id: uuid.UUID
    address_id: uuid.UUID


async def _seed_fixture_set(
    client: AsyncClient, engine: AsyncEngine, *, with_driver: bool
) -> _Fixtures:
    hasher = Argon2PasswordHasher(_settings_for_hasher())
    tenant_id, branch_id = await _seed_tenant_and_branch(engine)

    admin_email = f"{uuid.uuid4().hex}@auto-assign-smoke.example"
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

    if with_driver:
        await _seed_driver(engine, tenant_id=tenant_id, branch_id=branch_id)
        await _seed_vehicle(engine, tenant_id=tenant_id, branch_id=branch_id)

    cylinder_type_id = await _seed_cylinder_type(engine, tenant_id=tenant_id)
    await _seed_warehouse_with_stock(
        engine, tenant_id=tenant_id, branch_id=branch_id, cylinder_type_id=cylinder_type_id
    )
    await _seed_price_list(engine, tenant_id=tenant_id, cylinder_type_id=cylinder_type_id)
    customer_id, address_id = await _seed_customer(engine, tenant_id=tenant_id, branch_id=branch_id)

    return _Fixtures(
        tenant_id=tenant_id,
        branch_id=branch_id,
        admin_token=admin_token,
        cylinder_type_id=cylinder_type_id,
        customer_id=customer_id,
        address_id=address_id,
    )


async def _enable_auto_assignment(client: AsyncClient, headers: dict[str, str]) -> None:
    response = await client.post(
        "/api/v1/admin/tenant-configuration",
        json={"config_key": "auto_assignment_enabled", "config_value": True},
        headers=headers,
    )
    assert response.status_code == 201, response.text


async def _create_and_confirm_order(
    client: AsyncClient, fixtures: _Fixtures, headers: dict[str, str]
) -> dict[str, Any]:
    create_payload = {
        "branch_id": str(fixtures.branch_id),
        "customer_id": str(fixtures.customer_id),
        "address_id": str(fixtures.address_id),
        "delivery_address": {"address_line": "123 Test St"},
        "booking_source": "staff",
        "requested_date": datetime.now(UTC).isoformat(),
        "lines": [{"cylinder_type_id": str(fixtures.cylinder_type_id), "quantity": 2}],
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


async def _run_auto_assign_worker_burst(integration_settings: Settings) -> None:
    """Processes whatever `auto_assign_driver` jobs are currently queued,
    then exits — same burst-mode pattern `test_job_worker.py` uses for
    `ping`, against the same real `Database`/`JobQueue` the ARQ job
    function itself expects in `ctx`."""
    from arq.connections import RedisSettings
    from arq.worker import Worker

    from lpg.infrastructure.jobs.auto_assignment_jobs import auto_assign_driver
    from lpg.infrastructure.jobs.notification_jobs import send_notification
    from lpg.infrastructure.jobs.pool import JobQueue
    from lpg.infrastructure.persistence.database import build_database

    database = build_database(integration_settings)
    database.connect()
    job_queue = JobQueue(integration_settings)
    await job_queue.connect()
    try:
        # `send_notification` registered too -- the no-eligible-driver path
        # chains straight into it (`auto_assign_driver` enqueues it), same
        # as a real worker process would have both registered
        # (`WorkerSettings.functions`).
        worker = Worker(
            functions=[auto_assign_driver, send_notification],
            redis_settings=RedisSettings.from_dsn(str(integration_settings.redis_url)),
            burst=True,
            poll_delay=0,
            ctx={"database": database, "job_queue": job_queue},
        )
        await worker.main()
        await worker.close()
    finally:
        await database.disconnect()
        await job_queue.disconnect()


class TestAutoAssignmentThroughRealStack:
    async def test_confirming_an_order_auto_assigns_the_only_eligible_driver(
        self,
        stack: _AppAndClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        fixtures = await _seed_fixture_set(stack.client, admin_engine_lpg_test, with_driver=True)
        admin_headers = {"Authorization": f"Bearer {fixtures.admin_token}"}
        await _enable_auto_assignment(stack.client, admin_headers)

        confirmed = await _create_and_confirm_order(stack.client, fixtures, admin_headers)
        assert confirmed["status"] == "confirmed"

        await _run_auto_assign_worker_burst(integration_settings)

        order_response = await stack.client.get(
            f"/api/v1/orders/{confirmed['id']}", headers=admin_headers
        )
        assert order_response.status_code == 200, order_response.text
        order = order_response.json()
        assert order["status"] == "assigned"
        assert order["route_stop_id"] is not None

        audit_response = await stack.client.get(
            "/api/v1/admin/audit-log",
            params={"actor_id": "00000000-0000-0000-0000-0000000a0710"},
            headers=admin_headers,
        )
        assert audit_response.status_code == 200, audit_response.text
        entries = audit_response.json()["items"]
        assert entries
        assert all(e.get("actor_display_name") == "System (Auto-Assignment)" for e in entries)

    async def test_kill_switch_off_by_default_leaves_order_confirmed(
        self,
        stack: _AppAndClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        fixtures = await _seed_fixture_set(stack.client, admin_engine_lpg_test, with_driver=True)
        admin_headers = {"Authorization": f"Bearer {fixtures.admin_token}"}
        # `auto_assignment_enabled` deliberately never set — this is the
        # default state for every tenant.

        confirmed = await _create_and_confirm_order(stack.client, fixtures, admin_headers)
        await _run_auto_assign_worker_burst(integration_settings)

        order_response = await stack.client.get(
            f"/api/v1/orders/{confirmed['id']}", headers=admin_headers
        )
        assert order_response.json()["status"] == "confirmed"

    async def test_no_eligible_driver_leaves_order_confirmed_not_stuck(
        self,
        stack: _AppAndClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        fixtures = await _seed_fixture_set(stack.client, admin_engine_lpg_test, with_driver=False)
        admin_headers = {"Authorization": f"Bearer {fixtures.admin_token}"}
        await _enable_auto_assignment(stack.client, admin_headers)

        confirmed = await _create_and_confirm_order(stack.client, fixtures, admin_headers)
        await _run_auto_assign_worker_burst(integration_settings)

        order_response = await stack.client.get(
            f"/api/v1/orders/{confirmed['id']}", headers=admin_headers
        )
        # Nothing eligible -> a safe no-op, ready for the existing manual
        # assign flow -- never a crash, never a stuck/half-mutated order.
        assert order_response.json()["status"] == "confirmed"

        # The failure path isn't silent either -- the admin (an agency_admin,
        # in `_STAFF_ALERT_ROLES`) gets the `order_unassignable_staff`
        # in-app notification, the "ranked queue for human review" pattern.
        notifications_response = await stack.client.get(
            "/api/v1/notifications", headers=admin_headers
        )
        assert notifications_response.status_code == 200, notifications_response.text
        notifications = notifications_response.json()["items"]
        assert any(n["notification_type"] == "order_unassignable_staff" for n in notifications)
