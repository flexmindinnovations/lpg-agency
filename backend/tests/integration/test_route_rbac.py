"""RBAC and row-scoping coverage for the route permission codes.

Claims-based `require_permission` allow/deny per the exact matrix in
migration `de56730bb88f` (`_MANAGE_ROLES`/`_READ_ROLES`/`_DELIVER_ROLES`):
`routes:manage` -> `agency_admin`/`manager`/`dispatcher`, `routes:read`
additionally includes `driver`/`warehouse_staff`, `routes:deliver` is
`driver`-only. None of the route endpoints use `require_live_permission`
(unlike `orders:cancel_approve`/`reconciliation:approve`), so there is no
live-check class here, mirroring `test_inventory_rbac.py`'s structure minus
that piece.

The scoping classes exercise `_resolve_read_scope()`/`_route_in_scope()`
(`api/v1/routers/route.py`) through the real ASGI stack: a `driver` sees only
routes assigned to them, `dispatcher`/`manager` see only their branch, and
RLS backstops cross-tenant isolation independently of any of that
application-level filtering.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from lpg.api.v1.dependencies.identity import require_permission
from lpg.application.common.errors import PermissionDeniedError
from lpg.application.identity.principal import JwtAuthenticatedPrincipal
from lpg.infrastructure.identity.password_hasher import Argon2PasswordHasher

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration


def _principal(role: str, permission_code: str) -> JwtAuthenticatedPrincipal:
    return JwtAuthenticatedPrincipal(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        role=role,
        permission_codes=frozenset({permission_code}),
    )


class TestClaimsBasedChecks:
    async def test_allows_dispatcher_routes_manage(self) -> None:
        dependency = require_permission("routes:manage")
        result = await dependency(_principal("dispatcher", "routes:manage"))
        assert result.role == "dispatcher"

    async def test_denies_driver_routes_manage(self) -> None:
        dependency = require_permission("routes:manage")
        with pytest.raises(PermissionDeniedError):
            await dependency(_principal("driver", "routes:deliver"))

    async def test_denies_warehouse_staff_routes_manage(self) -> None:
        """`routes:read` includes `warehouse_staff`; `routes:manage` deliberately
        does not — mirrors `inventory:adjust`/`reconciliation:approve`'s own
        narrower-than-`:read` precedent.
        """
        dependency = require_permission("routes:manage")
        with pytest.raises(PermissionDeniedError):
            await dependency(_principal("warehouse_staff", "routes:read"))

    async def test_allows_driver_routes_read(self) -> None:
        dependency = require_permission("routes:read")
        result = await dependency(_principal("driver", "routes:read"))
        assert result.role == "driver"

    async def test_allows_warehouse_staff_routes_read(self) -> None:
        dependency = require_permission("routes:read")
        result = await dependency(_principal("warehouse_staff", "routes:read"))
        assert result.role == "warehouse_staff"

    async def test_denies_customer_routes_read(self) -> None:
        dependency = require_permission("routes:read")
        with pytest.raises(PermissionDeniedError):
            await dependency(_principal("customer", "orders:read"))

    async def test_allows_driver_routes_deliver(self) -> None:
        dependency = require_permission("routes:deliver")
        result = await dependency(_principal("driver", "routes:deliver"))
        assert result.role == "driver"

    async def test_denies_dispatcher_routes_deliver(self) -> None:
        dependency = require_permission("routes:deliver")
        with pytest.raises(PermissionDeniedError):
            await dependency(_principal("dispatcher", "routes:manage"))

    async def test_allows_agency_admin_routes_create(self) -> None:
        dependency = require_permission("routes:create")
        result = await dependency(_principal("agency_admin", "routes:create"))
        assert result.role == "agency_admin"

    async def test_denies_customer_routes_create(self) -> None:
        dependency = require_permission("routes:create")
        with pytest.raises(PermissionDeniedError):
            await dependency(_principal("customer", "orders:create"))


# ==========================================================================
# Real-stack scoping / cross-tenant isolation
# ==========================================================================


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

    # This suite seeds multiple synthetic users per test and logs each in —
    # well above `auth:login`'s 10/60s rate limit (keyed by client IP,
    # shared across every test in this module since they all originate from
    # the same ASGITransport "127.0.0.1"). Flushing isolates each test's
    # rate-limit counters, mirroring `test_order_endpoints_smoke.py`'s
    # `stack` fixture.
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


async def _seed_tenant_and_branch(
    engine: AsyncEngine, *, name: str = "Route RBAC Tenant"
) -> tuple[uuid.UUID, uuid.UUID]:
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), :name, :slug, 'ops@example.com') RETURNING id"
                ),
                {"name": name, "slug": f"route-rbac-{uuid.uuid4().hex[:10]}"},
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


async def _seed_branch(engine: AsyncEngine, *, tenant_id: uuid.UUID, name: str) -> uuid.UUID:
    async with engine.begin() as conn:
        branch_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.branch (id, tenant_id, name) "
                    "VALUES (gen_random_uuid(), :tenant_id, :name) RETURNING id"
                ),
                {"tenant_id": str(tenant_id), "name": name},
            )
        ).scalar_one()
    return uuid.UUID(str(branch_id))


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


async def _login(client: AsyncClient, *, email: str, password: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    access_token: str = response.json()["access_token"]
    return access_token


def _settings_for_hasher() -> Settings:
    from lpg.config.settings import Settings

    return Settings(environment="local", log_json=False)


async def _plan_route(
    client: AsyncClient,
    *,
    branch_id: uuid.UUID,
    driver_id: uuid.UUID,
    vehicle_id: uuid.UUID,
    headers: dict[str, str],
) -> str:
    response = await client.post(
        "/api/v1/routes",
        json={
            "branch_id": str(branch_id),
            "driver_id": str(driver_id),
            "vehicle_id": str(vehicle_id),
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    route_id: str = response.json()["id"]
    return route_id


class TestRoleScopedReads:
    async def test_driver_sees_only_their_own_route(
        self, real_lifespan_client: AsyncClient, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        client = real_lifespan_client
        hasher = Argon2PasswordHasher(_settings_for_hasher())
        tenant_id, branch_id = await _seed_tenant_and_branch(admin_engine_lpg_test)

        admin_email = f"{uuid.uuid4().hex}@route-rbac.example"
        admin_password = "correct horse battery staple 50"
        await _seed_staff_user(
            admin_engine_lpg_test,
            tenant_id=tenant_id,
            branch_id=branch_id,
            email=admin_email,
            password_hash=hasher.hash(admin_password),
            role="agency_admin",
        )
        admin_token = await _login(client, email=admin_email, password=admin_password)
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        driver_a_email = f"{uuid.uuid4().hex}@route-rbac.example"
        driver_a_password = "correct horse battery staple 51"
        driver_a_id = await _seed_driver(
            admin_engine_lpg_test,
            tenant_id=tenant_id,
            branch_id=branch_id,
            email=driver_a_email,
            password_hash=hasher.hash(driver_a_password),
        )
        driver_a_token = await _login(client, email=driver_a_email, password=driver_a_password)

        driver_b_email = f"{uuid.uuid4().hex}@route-rbac.example"
        driver_b_id = await _seed_driver(
            admin_engine_lpg_test,
            tenant_id=tenant_id,
            branch_id=branch_id,
            email=driver_b_email,
            password_hash=hasher.hash("correct horse battery staple 52"),
        )

        vehicle_id = await _seed_vehicle(
            admin_engine_lpg_test, tenant_id=tenant_id, branch_id=branch_id
        )

        own_route_id = await _plan_route(
            client,
            branch_id=branch_id,
            driver_id=driver_a_id,
            vehicle_id=vehicle_id,
            headers=admin_headers,
        )
        other_route_id = await _plan_route(
            client,
            branch_id=branch_id,
            driver_id=driver_b_id,
            vehicle_id=vehicle_id,
            headers=admin_headers,
        )

        driver_a_headers = {"Authorization": f"Bearer {driver_a_token}"}
        list_response = await client.get("/api/v1/routes", headers=driver_a_headers)
        assert list_response.status_code == 200, list_response.text
        route_ids = {r["id"] for r in list_response.json()["items"]}
        assert own_route_id in route_ids
        assert other_route_id not in route_ids

        get_own_response = await client.get(
            f"/api/v1/routes/{own_route_id}", headers=driver_a_headers
        )
        assert get_own_response.status_code == 200, get_own_response.text

        get_other_response = await client.get(
            f"/api/v1/routes/{other_route_id}", headers=driver_a_headers
        )
        assert get_other_response.status_code == 404, get_other_response.text

        active_response = await client.get(
            f"/api/v1/routes/active-for-driver/{driver_b_id}", headers=driver_a_headers
        )
        assert active_response.status_code == 404, active_response.text

    async def test_dispatcher_sees_only_their_branch(
        self, real_lifespan_client: AsyncClient, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        client = real_lifespan_client
        hasher = Argon2PasswordHasher(_settings_for_hasher())
        tenant_id, branch_a_id = await _seed_tenant_and_branch(admin_engine_lpg_test)
        branch_b_id = await _seed_branch(
            admin_engine_lpg_test, tenant_id=tenant_id, name="Other Branch"
        )

        admin_email = f"{uuid.uuid4().hex}@route-rbac.example"
        admin_password = "correct horse battery staple 53"
        await _seed_staff_user(
            admin_engine_lpg_test,
            tenant_id=tenant_id,
            branch_id=branch_a_id,
            email=admin_email,
            password_hash=hasher.hash(admin_password),
            role="agency_admin",
        )
        admin_token = await _login(client, email=admin_email, password=admin_password)
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        driver_a_id = await _seed_driver(
            admin_engine_lpg_test,
            tenant_id=tenant_id,
            branch_id=branch_a_id,
            email=f"{uuid.uuid4().hex}@route-rbac.example",
            password_hash=hasher.hash("correct horse battery staple 54"),
        )
        driver_b_id = await _seed_driver(
            admin_engine_lpg_test,
            tenant_id=tenant_id,
            branch_id=branch_b_id,
            email=f"{uuid.uuid4().hex}@route-rbac.example",
            password_hash=hasher.hash("correct horse battery staple 55"),
        )
        vehicle_a_id = await _seed_vehicle(
            admin_engine_lpg_test, tenant_id=tenant_id, branch_id=branch_a_id
        )
        vehicle_b_id = await _seed_vehicle(
            admin_engine_lpg_test, tenant_id=tenant_id, branch_id=branch_b_id
        )

        branch_a_route_id = await _plan_route(
            client,
            branch_id=branch_a_id,
            driver_id=driver_a_id,
            vehicle_id=vehicle_a_id,
            headers=admin_headers,
        )
        branch_b_route_id = await _plan_route(
            client,
            branch_id=branch_b_id,
            driver_id=driver_b_id,
            vehicle_id=vehicle_b_id,
            headers=admin_headers,
        )

        dispatcher_email = f"{uuid.uuid4().hex}@route-rbac.example"
        dispatcher_password = "correct horse battery staple 56"
        await _seed_staff_user(
            admin_engine_lpg_test,
            tenant_id=tenant_id,
            branch_id=branch_a_id,
            email=dispatcher_email,
            password_hash=hasher.hash(dispatcher_password),
            role="dispatcher",
        )
        dispatcher_token = await _login(
            client, email=dispatcher_email, password=dispatcher_password
        )
        dispatcher_headers = {"Authorization": f"Bearer {dispatcher_token}"}

        list_response = await client.get("/api/v1/routes", headers=dispatcher_headers)
        assert list_response.status_code == 200, list_response.text
        route_ids = {r["id"] for r in list_response.json()["items"]}
        assert branch_a_route_id in route_ids
        assert branch_b_route_id not in route_ids

        get_other_branch_response = await client.get(
            f"/api/v1/routes/{branch_b_route_id}", headers=dispatcher_headers
        )
        assert get_other_branch_response.status_code == 404, get_other_branch_response.text

    async def test_dispatcher_cannot_plan_a_route_outside_their_branch(
        self, real_lifespan_client: AsyncClient, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        """`routes:manage` is claims-based, not row-scoped by
        `require_permission` itself — `PlanRouteUseCase` accepts whatever
        `branch_id` the request body supplies. This documents that gap
        rather than asserting a 403 that the current implementation does
        not produce.
        """
        client = real_lifespan_client
        hasher = Argon2PasswordHasher(_settings_for_hasher())
        tenant_id, branch_a_id = await _seed_tenant_and_branch(admin_engine_lpg_test)
        branch_b_id = await _seed_branch(
            admin_engine_lpg_test, tenant_id=tenant_id, name="Other Branch"
        )

        dispatcher_email = f"{uuid.uuid4().hex}@route-rbac.example"
        dispatcher_password = "correct horse battery staple 57"
        await _seed_staff_user(
            admin_engine_lpg_test,
            tenant_id=tenant_id,
            branch_id=branch_a_id,
            email=dispatcher_email,
            password_hash=hasher.hash(dispatcher_password),
            role="dispatcher",
        )
        dispatcher_token = await _login(
            client, email=dispatcher_email, password=dispatcher_password
        )
        dispatcher_headers = {"Authorization": f"Bearer {dispatcher_token}"}

        driver_id = await _seed_driver(
            admin_engine_lpg_test,
            tenant_id=tenant_id,
            branch_id=branch_b_id,
            email=f"{uuid.uuid4().hex}@route-rbac.example",
            password_hash=hasher.hash("correct horse battery staple 58"),
        )
        vehicle_id = await _seed_vehicle(
            admin_engine_lpg_test, tenant_id=tenant_id, branch_id=branch_b_id
        )

        response = await client.post(
            "/api/v1/routes",
            json={
                "branch_id": str(branch_b_id),
                "driver_id": str(driver_id),
                "vehicle_id": str(vehicle_id),
            },
            headers=dispatcher_headers,
        )
        assert response.status_code == 201, response.text
        assert response.json()["branch_id"] == str(branch_b_id)


class TestCrossTenantIsolation:
    async def test_another_tenants_admin_cannot_see_this_route(
        self, real_lifespan_client: AsyncClient, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        client = real_lifespan_client
        hasher = Argon2PasswordHasher(_settings_for_hasher())
        tenant_id, branch_id = await _seed_tenant_and_branch(admin_engine_lpg_test)

        admin_email = f"{uuid.uuid4().hex}@route-rbac.example"
        admin_password = "correct horse battery staple 59"
        await _seed_staff_user(
            admin_engine_lpg_test,
            tenant_id=tenant_id,
            branch_id=branch_id,
            email=admin_email,
            password_hash=hasher.hash(admin_password),
            role="agency_admin",
        )
        admin_token = await _login(client, email=admin_email, password=admin_password)
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        driver_id = await _seed_driver(
            admin_engine_lpg_test,
            tenant_id=tenant_id,
            branch_id=branch_id,
            email=f"{uuid.uuid4().hex}@route-rbac.example",
            password_hash=hasher.hash("correct horse battery staple 60"),
        )
        vehicle_id = await _seed_vehicle(
            admin_engine_lpg_test, tenant_id=tenant_id, branch_id=branch_id
        )
        route_id = await _plan_route(
            client,
            branch_id=branch_id,
            driver_id=driver_id,
            vehicle_id=vehicle_id,
            headers=admin_headers,
        )

        other_tenant_id, other_branch_id = await _seed_tenant_and_branch(
            admin_engine_lpg_test, name="Route RBAC Other Tenant"
        )
        other_admin_email = f"{uuid.uuid4().hex}@route-rbac.example"
        other_admin_password = "correct horse battery staple 61"
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

        get_response = await client.get(f"/api/v1/routes/{route_id}", headers=other_headers)
        assert get_response.status_code == 404, get_response.text

        list_response = await client.get("/api/v1/routes", headers=other_headers)
        assert list_response.status_code == 200, list_response.text
        assert route_id not in {r["id"] for r in list_response.json()["items"]}
