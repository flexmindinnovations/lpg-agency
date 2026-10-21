"""Smoke tests for the complaint router, through the real ASGI stack.

C4 in `planning/MODULE_STATUS.md` found `complaint`, `employee`, `invoice` and
`reporting` shipped with zero test files. This file is `complaint`'s share of
R7 (`reporting`'s own share landed as R7a).

Exercising the full raise→assign→resolve→get lifecycle against a real
database surfaced a genuine, previously-uncaught bug: `ComplaintAssignment`/
`ComplaintResolution` are `Entity` subclasses whose `@dataclass`-generated
`__init__` never calls `Entity.__init__` or sets its `_id` slot, so `.id`
raised `AttributeError` — on every access. That broke two things
independently: `SqlAlchemyComplaintRepository.save()`'s assignment-merge
lookup (`existing_assignments.get(domain_a.id)`), which crashed
`POST /complaints/{id}/assign` and `/resolve` outright, and
`ComplaintAssignmentResponse`/`ComplaintResolutionResponse` serialization,
which would have crashed `GET /complaints/{id}` for any complaint with an
assignment or resolution even if the first bug were fixed. Both are fixed in
`domain/complaint/complaint.py` (an `.id` property reading `entity_id`) as
part of this same change — a domain-only unit test could not have caught the
`save()` half, since that only breaks through the real repository/session.

The two GET endpoints carry no `require_permission` dependency at all (see
`test_complaint_rbac.py`'s docstring) — `test_get_and_list_reachable_without_
complaints_manage` documents that as observed behavior, not asserts it's
correct.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

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
def admin_engine_lpg_test(admin_engine: AsyncEngine) -> AsyncEngine:
    """The superuser engine for the test database the app under test uses
    (`LPG_TEST_ADMIN_DATABASE_URL`), so seeded rows are visible to it."""
    return admin_engine


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
                {"name": tenant_name, "slug": f"complaint-smoke-{uuid.uuid4().hex[:10]}"},
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


async def _seed_customer(engine: AsyncEngine, *, tenant_id: uuid.UUID) -> uuid.UUID:
    async with engine.begin() as conn:
        branch_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.branch (id, tenant_id, name) "
                    "VALUES (gen_random_uuid(), :tenant_id, 'Main Branch') RETURNING id"
                ),
                {"tenant_id": str(tenant_id)},
            )
        ).scalar_one()
        customer_id = (
            await conn.execute(
                text(
                    "INSERT INTO customer.customer "
                    "(id, tenant_id, branch_id, customer_type, full_name, phone_number, "
                    "consumer_number) VALUES (gen_random_uuid(), :tenant_id, :branch_id, "
                    "'domestic', 'Meena Iyer', :phone, :consumer_number) RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id),
                    "phone": f"+91{uuid.uuid4().int % 10**9:09d}",
                    "consumer_number": f"CN{uuid.uuid4().hex[:10]}",
                },
            )
        ).scalar_one()
    return uuid.UUID(str(customer_id))


async def _user_id(engine: AsyncEngine, email: str) -> uuid.UUID:
    async with engine.begin() as conn:
        user_id = (
            await conn.execute(
                text("SELECT id FROM identity.identity_user WHERE email = :email"),
                {"email": email},
            )
        ).scalar_one()
    return uuid.UUID(str(user_id))


async def _login(client: AsyncClient, *, email: str, password: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    access_token: str = response.json()["access_token"]
    return access_token


class TestComplaintLifecycleThroughTheRealStack:
    async def test_raise_assign_resolve_and_get_full_lifecycle(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        hasher = Argon2PasswordHasher(integration_settings)
        email = f"{uuid.uuid4().hex}@complaint-smoke.example"
        password = "correct horse battery staple 42"
        tenant_id = await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="manager",
            tenant_name="Complaint Smoke Tenant (lifecycle)",
        )
        customer_id = await _seed_customer(admin_engine_lpg_test, tenant_id=tenant_id)
        manager_id = await _user_id(admin_engine_lpg_test, email)
        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}
        client = real_lifespan_client

        unknown_customer = await client.post(
            "/api/v1/complaints",
            headers=headers,
            json={
                "customer_id": str(uuid.uuid4()),
                "category": "Other",
                "priority": "Low",
                "description": "Nobody",
            },
        )
        assert unknown_customer.status_code == 422, unknown_customer.text

        assignees = await client.get("/api/v1/complaints/assignees", headers=headers)
        assert assignees.status_code == 200, assignees.text
        assert manager_id in [uuid.UUID(a["user_id"]) for a in assignees.json()]

        raise_response = await client.post(
            "/api/v1/complaints",
            headers=headers,
            json={
                "customer_id": str(customer_id),
                "category": "LateDelivery",
                "priority": "High",
                "description": "Cylinder arrived a day late.",
            },
        )
        assert raise_response.status_code == 201, raise_response.text
        complaint_id = raise_response.json()["id"]

        stranger = await client.post(
            f"/api/v1/complaints/{complaint_id}/assign",
            headers=headers,
            json={"assigned_to": str(uuid.uuid4())},
        )
        assert stranger.status_code == 422, stranger.text
        assign_response = await client.post(
            f"/api/v1/complaints/{complaint_id}/assign",
            headers=headers,
            json={"assigned_to": str(manager_id)},
        )
        assert assign_response.status_code == 204, assign_response.text

        resolve_response = await client.post(
            f"/api/v1/complaints/{complaint_id}/resolve",
            headers=headers,
            json={"outcome": "Resolved", "resolution_notes": "Replacement dispatched."},
        )
        assert resolve_response.status_code == 204, resolve_response.text

        get_response = await client.get(f"/api/v1/complaints/{complaint_id}", headers=headers)
        assert get_response.status_code == 200, get_response.text
        body = get_response.json()
        assert body["status"] == "Resolved"
        assert len(body["assignments"]) == 1
        assert body["resolution"]["outcome"] == "Resolved"
        assert body["resolution"]["resolution_notes"] == "Replacement dispatched."
        assert body["customer_name"] == "Meena Iyer"
        assert body["assignee_name"] == email

    async def test_list_complaints_is_tenant_scoped(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        hasher = Argon2PasswordHasher(integration_settings)
        password = "correct horse battery staple 42"

        email = f"{uuid.uuid4().hex}@complaint-smoke.example"
        own_tenant = await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="manager",
            tenant_name="Complaint Smoke Tenant (list, own)",
        )
        own_customer = await _seed_customer(admin_engine_lpg_test, tenant_id=own_tenant)
        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}

        raise_response = await real_lifespan_client.post(
            "/api/v1/complaints",
            headers=headers,
            json={
                "customer_id": str(own_customer),
                "category": "Other",
                "priority": "Low",
                "description": "own tenant's complaint",
            },
        )
        assert raise_response.status_code == 201, raise_response.text

        other_email = f"{uuid.uuid4().hex}@complaint-smoke.example"
        other_tenant = await _seed_staff_user(
            admin_engine_lpg_test,
            email=other_email,
            password_hash=hasher.hash(password),
            role="manager",
            tenant_name="Complaint Smoke Tenant (list, other)",
        )
        other_customer = await _seed_customer(admin_engine_lpg_test, tenant_id=other_tenant)
        other_token = await _login(real_lifespan_client, email=other_email, password=password)
        other_headers = {"Authorization": f"Bearer {other_token}"}
        other_raise_response = await real_lifespan_client.post(
            "/api/v1/complaints",
            headers=other_headers,
            json={
                "customer_id": str(other_customer),
                "category": "Other",
                "priority": "Low",
                "description": "other tenant's complaint",
            },
        )
        assert other_raise_response.status_code == 201, other_raise_response.text

        list_response = await real_lifespan_client.get("/api/v1/complaints", headers=headers)
        assert list_response.status_code == 200, list_response.text
        body = list_response.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["description"] == "own tenant's complaint"

    async def test_get_unknown_complaint_returns_404(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        hasher = Argon2PasswordHasher(integration_settings)
        email = f"{uuid.uuid4().hex}@complaint-smoke.example"
        password = "correct horse battery staple 42"
        await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="manager",
            tenant_name="Complaint Smoke Tenant (404)",
        )
        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}

        response = await real_lifespan_client.get(
            f"/api/v1/complaints/{uuid.uuid4()}", headers=headers
        )
        assert response.status_code == 404, response.text

    async def test_raise_complaint_denied_without_complaints_manage(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        """`warehouse_staff` is not among `b05967dbc83e`'s granted roles."""
        hasher = Argon2PasswordHasher(integration_settings)
        email = f"{uuid.uuid4().hex}@complaint-smoke.example"
        password = "correct horse battery staple 42"
        await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="warehouse_staff",
            tenant_name="Complaint Smoke Tenant (denied)",
        )
        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}

        response = await real_lifespan_client.post(
            "/api/v1/complaints",
            headers=headers,
            json={
                "customer_id": str(uuid.uuid4()),
                "category": "Other",
                "priority": "Low",
                "description": "n/a",
            },
        )
        assert response.status_code == 403, response.text

    async def test_get_and_list_denied_without_complaints_manage(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        """Was `test_get_and_list_reachable_without_complaints_manage`,
        which documented (its own docstring said so explicitly) rather than
        asserted the old behavior was correct: the two GET endpoints had no
        `require_permission` dependency at all, so any authenticated tenant
        member — including one without `complaints.manage`, like
        `warehouse_staff` here — could read any complaint. Fixed alongside
        adding `customer`-role ownership scoping to the same two endpoints
        (a `customer` principal forced onto their own `customer_id`,
        mirroring `order.py`'s `_resolve_scope` pattern) — same permission
        `raise_complaint`/`assign_complaint`/`resolve_complaint` already
        required, now consistently required for read too.
        """
        hasher = Argon2PasswordHasher(integration_settings)
        email = f"{uuid.uuid4().hex}@complaint-smoke.example"
        password = "correct horse battery staple 42"
        await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="warehouse_staff",
            tenant_name="Complaint Smoke Tenant (get/list denied)",
        )
        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}

        list_response = await real_lifespan_client.get("/api/v1/complaints", headers=headers)
        assert list_response.status_code == 403, list_response.text

        get_response = await real_lifespan_client.get(
            f"/api/v1/complaints/{uuid.uuid4()}", headers=headers
        )
        assert get_response.status_code == 403, get_response.text
