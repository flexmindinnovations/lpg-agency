"""One happy path per inventory router endpoint, through the real ASGI stack."""

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
) -> uuid.UUID:
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'Inventory Smoke Tenant', :slug, "
                    "'ops@example.com') RETURNING id"
                ),
                {"slug": f"inv-smoke-{uuid.uuid4().hex[:10]}"},
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


async def _seed_warehouse_and_cylinder_type(
    engine: AsyncEngine, *, tenant_id: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID]:
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
        cylinder_type_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.cylinder_type (id, tenant_id, name, weight_kg) "
                    "VALUES (gen_random_uuid(), :tenant_id, '14.2kg', 14.2) RETURNING id"
                ),
                {"tenant_id": str(tenant_id)},
            )
        ).scalar_one()
    return uuid.UUID(str(warehouse_id)), uuid.UUID(str(cylinder_type_id))


async def _seed_vehicle(engine: AsyncEngine, *, tenant_id: uuid.UUID) -> uuid.UUID:
    async with engine.begin() as conn:
        branch_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.branch (id, tenant_id, name) "
                    "VALUES (gen_random_uuid(), :tenant_id, 'Vehicle Branch') RETURNING id"
                ),
                {"tenant_id": str(tenant_id)},
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
    return uuid.UUID(str(vehicle_id))


async def _login(client: AsyncClient, *, email: str, password: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    access_token: str = response.json()["access_token"]
    return access_token


class TestInventoryEndpointsThroughRealStack:
    async def test_inventory_lifecycle_smoke(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        email = f"{uuid.uuid4().hex}@inv-smoke.example"
        password = "correct horse battery staple 42"
        hasher = Argon2PasswordHasher(integration_settings)
        tenant_id = await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="agency_admin",
        )
        warehouse_id, cylinder_type_id = await _seed_warehouse_and_cylinder_type(
            admin_engine_lpg_test, tenant_id=tenant_id
        )
        vehicle_id = await _seed_vehicle(admin_engine_lpg_test, tenant_id=tenant_id)

        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}
        client = real_lifespan_client

        # 1. Balance on a never-touched warehouse -> all-zero, not 404.
        balance_response = await client.get(
            f"/api/v1/inventory-locations/warehouse/{warehouse_id}/balance", headers=headers
        )
        assert balance_response.status_code == 200, balance_response.text
        assert balance_response.json()["balances"] == []

        # 2. Goods receipt -> credits Filled.
        grn_response = await client.post(
            f"/api/v1/warehouses/{warehouse_id}/goods-receipt-notes",
            json={"cylinder_type_id": str(cylinder_type_id), "quantity_received": 100},
            headers=headers,
        )
        assert grn_response.status_code == 201, grn_response.text
        assert grn_response.json()["quantity_received"] == 100

        # 3. Load transfer warehouse -> vehicle.
        transfer_response = await client.post(
            "/api/v1/inventory/load-transfers",
            json={
                "warehouse_id": str(warehouse_id),
                "vehicle_id": str(vehicle_id),
                "lines": [
                    {"cylinder_type_id": str(cylinder_type_id), "status": "filled", "quantity": 40}
                ],
            },
            headers=headers,
        )
        assert transfer_response.status_code == 201, transfer_response.text
        warehouse_balance = {
            (line["cylinder_type_id"], line["status"]): line["quantity"]
            for line in transfer_response.json()["warehouse_balance"]["balances"]
        }
        vehicle_balance = {
            (line["cylinder_type_id"], line["status"]): line["quantity"]
            for line in transfer_response.json()["vehicle_balance"]["balances"]
        }
        assert warehouse_balance[(str(cylinder_type_id), "filled")] == 60
        assert vehicle_balance[(str(cylinder_type_id), "filled")] == 40

        # 4. Delivery then collection move independently (BR-13).
        delivery_response = await client.post(
            f"/api/v1/vehicles/{vehicle_id}/deliveries",
            json={"cylinder_type_id": str(cylinder_type_id), "quantity": 15},
            headers=headers,
        )
        assert delivery_response.status_code == 201, delivery_response.text

        collection_response = await client.post(
            f"/api/v1/vehicles/{vehicle_id}/collections",
            json={"cylinder_type_id": str(cylinder_type_id), "quantity": 14},
            headers=headers,
        )
        assert collection_response.status_code == 201, collection_response.text
        collection_balance = {
            (line["cylinder_type_id"], line["status"]): line["quantity"]
            for line in collection_response.json()["balances"]
        }
        assert collection_balance[(str(cylinder_type_id), "filled")] == 25
        assert collection_balance[(str(cylinder_type_id), "empty")] == 14

        # 5. Valid status chain on the vehicle: empty -> damaged -> quarantine.
        status_change_response = await client.post(
            f"/api/v1/inventory-locations/vehicle/{vehicle_id}/status-changes",
            json={
                "cylinder_type_id": str(cylinder_type_id),
                "from_status": "empty",
                "to_status": "damaged",
                "quantity": 5,
            },
            headers=headers,
        )
        assert status_change_response.status_code == 201, status_change_response.text

        # 6. Invalid transition -> 409 INVALID_STATUS_TRANSITION.
        invalid_transition_response = await client.post(
            f"/api/v1/inventory-locations/vehicle/{vehicle_id}/status-changes",
            json={
                "cylinder_type_id": str(cylinder_type_id),
                "from_status": "filled",
                "to_status": "empty",
                "quantity": 1,
            },
            headers=headers,
        )
        assert invalid_transition_response.status_code == 409, invalid_transition_response.text
        assert invalid_transition_response.json()["error_code"] == "INVALID_STATUS_TRANSITION"

        # 7. Adjustment exceeding stock -> 409 INSUFFICIENT_STOCK.
        insufficient_response = await client.post(
            f"/api/v1/inventory-locations/vehicle/{vehicle_id}/adjustments",
            json={
                "cylinder_type_id": str(cylinder_type_id),
                "from_status": "filled",
                "to_status": "leakage",
                "quantity": 999,
                "reason": "test",
            },
            headers=headers,
        )
        assert insufficient_response.status_code == 409, insufficient_response.text
        assert insufficient_response.json()["error_code"] == "INSUFFICIENT_STOCK"

        # 8. Successful adjustment.
        adjust_response = await client.post(
            f"/api/v1/inventory-locations/vehicle/{vehicle_id}/adjustments",
            json={
                "cylinder_type_id": str(cylinder_type_id),
                "from_status": "filled",
                "to_status": "leakage",
                "quantity": 2,
                "reason": "Found a slow leak during inspection",
            },
            headers=headers,
        )
        assert adjust_response.status_code == 201, adjust_response.text

        # 9. Create + approve a reconciliation record.
        reconciliation_response = await client.post(
            f"/api/v1/inventory-locations/vehicle/{vehicle_id}/reconciliation-records",
            json={
                "cylinder_type_id": str(cylinder_type_id),
                "status": "filled",
                "actual_quantity": 20,
            },
            headers=headers,
        )
        assert reconciliation_response.status_code == 201, reconciliation_response.text
        record = reconciliation_response.json()
        assert record["expected_quantity"] == 23
        assert record["actual_quantity"] == 20
        assert record["variance"] == -3
        assert record["approved_by"] is None

        approve_response = await client.post(
            f"/api/v1/reconciliation-records/{record['id']}/approve", headers=headers
        )
        assert approve_response.status_code == 200, approve_response.text
        assert approve_response.json()["approved_by"] is not None

        # 10. Transaction history is populated and cursor-paginated.
        transactions_response = await client.get(
            f"/api/v1/inventory-locations/vehicle/{vehicle_id}/transactions?limit=3",
            headers=headers,
        )
        assert transactions_response.status_code == 200, transactions_response.text
        page = transactions_response.json()
        assert len(page["items"]) == 3
        assert page["next_cursor"] is not None
