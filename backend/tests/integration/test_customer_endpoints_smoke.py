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
    engine: AsyncEngine, *, email: str, password_hash: str, role: str
) -> tuple[uuid.UUID, uuid.UUID]:
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'Customer Smoke Tenant', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"cust-smoke-{uuid.uuid4().hex[:10]}"},
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
    return uuid.UUID(str(tenant_id)), uuid.UUID(str(user_id))


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


async def _login(client: AsyncClient, *, email: str, password: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    access_token: str = response.json()["access_token"]
    return access_token


class TestCustomerEndpointsThroughRealStack:
    async def test_staff_customer_lifecycle_smoke(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        email = f"{uuid.uuid4().hex}@cust-smoke.example"
        password = "correct horse battery staple 42"
        hasher = Argon2PasswordHasher(integration_settings)
        tenant_id, _user_id = await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="agency_admin",
        )
        branch_id = await _seed_branch(
            admin_engine_lpg_test, tenant_id=tenant_id, name="North Branch"
        )

        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Register Customer
        register_response = await real_lifespan_client.post(
            "/api/v1/customers",
            json={
                "branch_id": str(branch_id),
                "consumer_number": f"CN-{uuid.uuid4().hex[:6]}",
                "full_name": "Ramesh Patil",
                "phone_number": "+919876543210",
                "customer_type": "domestic",
                "line_1": "123 High Street",
            },
            headers=headers,
        )
        assert register_response.status_code == 200, register_response.text
        customer_id = register_response.json()["id"]

        # 2. Get Customer Details
        get_response = await real_lifespan_client.get(
            f"/api/v1/customers/{customer_id}",
            headers=headers,
        )
        assert get_response.status_code == 200, get_response.text
        assert get_response.json()["full_name"] == "Ramesh Patil"
        assert len(get_response.json()["addresses"]) == 1

        # 3. Submit KYC Document
        kyc_response = await real_lifespan_client.post(
            f"/api/v1/customers/{customer_id}/kyc",
            json={
                "doc_type": "aadhaar",
                "document_number": "AADHAAR-REF-123",
            },
            headers=headers,
        )
        assert kyc_response.status_code == 200, kyc_response.text
        doc_id = kyc_response.json()

        # 4. Verify KYC Document
        verify_response = await real_lifespan_client.post(
            f"/api/v1/customers/{customer_id}/kyc/{doc_id}/verify",
            json={"status": "verified"},
            headers=headers,
        )
        assert verify_response.status_code == 200, verify_response.text

        # 5. List/Search Customers
        list_response = await real_lifespan_client.get(
            "/api/v1/customers?search=Ramesh",
            headers=headers,
        )
        assert list_response.status_code == 200, list_response.text
        assert list_response.json()["total"] == 1
        assert list_response.json()["items"][0]["full_name"] == "Ramesh Patil"
        assert list_response.json()["items"][0]["kyc_status"] == "verified"

    async def test_next_consumer_number_and_lpg_subsidy_id_smoke(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        email = f"{uuid.uuid4().hex}@cust-smoke.example"
        password = "correct horse battery staple 42"
        hasher = Argon2PasswordHasher(integration_settings)
        tenant_id, _user_id = await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="agency_admin",
        )
        branch_id = await _seed_branch(
            admin_engine_lpg_test, tenant_id=tenant_id, name="Sequence Branch"
        )
        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Peek the suggested Consumer Number
        peek_response = await real_lifespan_client.post(
            "/api/v1/customers/next-consumer-number", headers=headers
        )
        assert peek_response.status_code == 200, peek_response.text
        suggested = peek_response.json()["consumer_number"]
        assert suggested.startswith("CN-")

        # 2. Register a customer using the suggested number and a valid LPG ID
        register_response = await real_lifespan_client.post(
            "/api/v1/customers",
            json={
                "branch_id": str(branch_id),
                "consumer_number": suggested,
                "full_name": "Sunita Verma",
                "phone_number": f"+91{uuid.uuid4().int % 10**10:010d}",
                "customer_type": "domestic",
                "lpg_subsidy_id": "11122233344455566",
            },
            headers=headers,
        )
        assert register_response.status_code == 200, register_response.text
        assert register_response.json()["lpg_subsidy_id"] == "11122233344455566"

        # 3. A second customer reusing the same LPG ID is rejected
        duplicate_response = await real_lifespan_client.post(
            "/api/v1/customers",
            json={
                "branch_id": str(branch_id),
                "consumer_number": f"CN-{uuid.uuid4().hex[:6]}",
                "full_name": "Another Person",
                "phone_number": f"+91{uuid.uuid4().int % 10**10:010d}",
                "customer_type": "domestic",
                "lpg_subsidy_id": "11122233344455566",
            },
            headers=headers,
        )
        assert duplicate_response.status_code == 409, duplicate_response.text
        assert duplicate_response.json()["error_code"] == "DUPLICATE_LPG_SUBSIDY_ID"

        # 4. Peeking again suggests the next number in sequence
        peek_again_response = await real_lifespan_client.post(
            "/api/v1/customers/next-consumer-number", headers=headers
        )
        assert peek_again_response.status_code == 200, peek_again_response.text
        assert peek_again_response.json()["consumer_number"] != suggested
