"""Stale-unassigned-order alert, through the real ASGI stack + a real
Postgres session + a real Redis-backed ARQ worker — not mocks.

`check_stale_unassigned_orders` is a cron job (time-triggered, not
event-triggered like `auto_assign_driver`) — there's nothing meaningful
to simulate about ARQ's own scheduling here, so it's called directly with
a plain `ctx` dict, the same shape ARQ would actually hand it. What *is*
real: a genuine order confirmed through the API, its `order_status_
history` row backdated via direct SQL to simulate staleness (the API
itself always stamps `changed_at` as `now()` — there's no other way to
get a "confirmed 5 hours ago" row), the job's own Postgres query against
that real data, and the resulting `send_notification` job actually
processed by a burst-mode `arq.worker.Worker`.
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
        "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:5433/lpg_test"
    )
    try:
        yield engine
    finally:
        await engine.dispose()


# ==========================================================================
# Seed helpers — self-contained duplicate of `test_auto_assignment_jobs_
# smoke.py`'s own (same self-containment convention this test suite
# already follows everywhere -- no cross-test-file imports anywhere).
# ==========================================================================


async def _seed_tenant_and_branch(engine: AsyncEngine) -> tuple[uuid.UUID, uuid.UUID]:
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'Stale Order Smoke Tenant', :slug, "
                    "'ops@example.com') RETURNING id"
                ),
                {"slug": f"stale-order-smoke-{uuid.uuid4().hex[:10]}"},
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
        # `EmployeeBranchStaffResolver` resolves branch staff via
        # `tenant.employee` -> phone number -> `identity.identity_user`.
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
                    "'Stale Order Smoke Customer', :phone, :consumer_number) RETURNING id"
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


async def _seed_fixture_set(client: AsyncClient, engine: AsyncEngine) -> _Fixtures:
    hasher = Argon2PasswordHasher(_settings_for_hasher())
    tenant_id, branch_id = await _seed_tenant_and_branch(engine)

    admin_email = f"{uuid.uuid4().hex}@stale-order-smoke.example"
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


async def _backdate_confirmed_at(engine: AsyncEngine, *, order_id: str, hours_ago: float) -> None:
    """The API always stamps `order_status_history.changed_at` as
    `now()` -- direct SQL is the only way to simulate "confirmed N hours
    ago" for this test."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE orders.order_status_history SET changed_at = :changed_at "
                "WHERE order_id = :order_id AND to_status = 'confirmed'"
            ),
            {
                "order_id": order_id,
                "changed_at": datetime.now(UTC) - timedelta(hours=hours_ago),
            },
        )


async def _run_stale_order_check(integration_settings: Settings) -> None:
    """Calls the cron job function directly with a plain `ctx` dict --
    ARQ's own time-based scheduling has nothing meaningful to simulate
    here; what matters is the job's own query/notify/mark logic against
    real data, which this exercises exactly as ARQ would call it."""
    from lpg.infrastructure.jobs.pool import JobQueue
    from lpg.infrastructure.jobs.stale_order_jobs import check_stale_unassigned_orders
    from lpg.infrastructure.persistence.database import build_database

    database = build_database(integration_settings)
    database.connect()
    job_queue = JobQueue(integration_settings)
    await job_queue.connect()
    try:
        await check_stale_unassigned_orders({"database": database, "job_queue": job_queue})
    finally:
        await database.disconnect()
        await job_queue.disconnect()


async def _run_send_notification_worker_burst(integration_settings: Settings) -> None:
    from arq.connections import RedisSettings
    from arq.worker import Worker

    from lpg.infrastructure.jobs.notification_jobs import send_notification
    from lpg.infrastructure.jobs.pool import JobQueue
    from lpg.infrastructure.persistence.database import build_database

    database = build_database(integration_settings)
    database.connect()
    job_queue = JobQueue(integration_settings)
    await job_queue.connect()
    try:
        worker = Worker(
            functions=[send_notification],
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


class TestStaleUnassignedOrderAlertThroughRealStack:
    async def test_stale_confirmed_order_notifies_branch_staff(
        self,
        stack: _AppAndClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        fixtures = await _seed_fixture_set(stack.client, admin_engine_lpg_test)
        admin_headers = {"Authorization": f"Bearer {fixtures.admin_token}"}

        confirmed = await _create_and_confirm_order(stack.client, fixtures, admin_headers)
        # Default threshold is 4 hours (DEFAULT_STALE_HOURS) -- backdate
        # past it.
        await _backdate_confirmed_at(admin_engine_lpg_test, order_id=confirmed["id"], hours_ago=5)

        await _run_stale_order_check(integration_settings)
        await _run_send_notification_worker_burst(integration_settings)

        notifications_response = await stack.client.get(
            "/api/v1/notifications", headers=admin_headers
        )
        assert notifications_response.status_code == 200, notifications_response.text
        notifications = notifications_response.json()["items"]
        assert any(n["notification_type"] == "order_stale_unassigned_staff" for n in notifications)

        order_response = await stack.client.get(
            f"/api/v1/orders/{confirmed['id']}", headers=admin_headers
        )
        assert order_response.json()["status"] == "confirmed"

    async def test_recently_confirmed_order_is_not_flagged(
        self,
        stack: _AppAndClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        fixtures = await _seed_fixture_set(stack.client, admin_engine_lpg_test)
        admin_headers = {"Authorization": f"Bearer {fixtures.admin_token}"}

        await _create_and_confirm_order(stack.client, fixtures, admin_headers)
        # No backdating -- confirmed just now, well inside the 4-hour
        # default threshold.

        await _run_stale_order_check(integration_settings)
        await _run_send_notification_worker_burst(integration_settings)

        notifications_response = await stack.client.get(
            "/api/v1/notifications", headers=admin_headers
        )
        notifications = notifications_response.json()["items"]
        assert not any(
            n["notification_type"] == "order_stale_unassigned_staff" for n in notifications
        )

    async def test_a_second_run_inside_the_same_window_does_not_renotify(
        self,
        stack: _AppAndClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        fixtures = await _seed_fixture_set(stack.client, admin_engine_lpg_test)
        admin_headers = {"Authorization": f"Bearer {fixtures.admin_token}"}

        confirmed = await _create_and_confirm_order(stack.client, fixtures, admin_headers)
        await _backdate_confirmed_at(admin_engine_lpg_test, order_id=confirmed["id"], hours_ago=5)

        await _run_stale_order_check(integration_settings)
        await _run_send_notification_worker_burst(integration_settings)
        notifications_response = await stack.client.get(
            "/api/v1/notifications", headers=admin_headers
        )
        first_count = sum(
            1
            for n in notifications_response.json()["items"]
            if n["notification_type"] == "order_stale_unassigned_staff"
        )
        assert first_count == 1

        # Second tick, same hour -- `last_stale_notified_at` was just set,
        # so the repository's own re-notify guard should exclude this
        # order this time.
        await _run_stale_order_check(integration_settings)
        await _run_send_notification_worker_burst(integration_settings)
        notifications_response = await stack.client.get(
            "/api/v1/notifications", headers=admin_headers
        )
        second_count = sum(
            1
            for n in notifications_response.json()["items"]
            if n["notification_type"] == "order_stale_unassigned_staff"
        )
        assert second_count == 1
