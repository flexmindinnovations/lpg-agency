"""QA fixes DA-02 / DA-04 / DA-34 through the real stack.

- A stock count changes nothing until someone other than the counter
  approves it; approval books the variance exactly once; reject leaves stock
  alone; another tenant cannot see or decide the count.
- Goods receipt takes the OMC as a code and its document numbers; an unknown
  OMC is a 422, never a 500.
- Empties go back to the OMC with a numbered return note, and the stock
  register shows the day's opening, receipts, issues and closing.

Uses the env-var database fixtures (`admin_engine`, `integration_settings`).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

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

_PASSWORD = "correct horse battery staple 42"


@pytest.fixture
async def client(
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


async def _seed_tenant(engine: AsyncEngine) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """A tenant with one warehouse and one cylinder type."""
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'Count Approval Tenant', :slug, "
                    "'ops@example.com') RETURNING id"
                ),
                {"slug": f"count-{uuid.uuid4().hex[:10]}"},
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
        cylinder_type_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.cylinder_type (id, tenant_id, name, weight_kg) "
                    "VALUES (gen_random_uuid(), :tenant_id, '14.2kg', 14.2) RETURNING id"
                ),
                {"tenant_id": str(tenant_id)},
            )
        ).scalar_one()
    return (
        uuid.UUID(str(tenant_id)),
        uuid.UUID(str(warehouse_id)),
        uuid.UUID(str(cylinder_type_id)),
    )


async def _staff_token(
    client: AsyncClient,
    engine: AsyncEngine,
    settings: Settings,
    *,
    tenant_id: uuid.UUID,
    role: str,
) -> dict[str, str]:
    email = f"{uuid.uuid4().hex}@count-approval.example"
    password_hash = Argon2PasswordHasher(settings).hash(_PASSWORD)
    async with engine.begin() as conn:
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
                "FROM identity.role_permission rp JOIN identity.role r ON r.id = rp.role_id "
                "WHERE r.code = :role"
            ),
            {"user_id": user_id, "role": role},
        )
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": _PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _filled(
    client: AsyncClient, headers: dict[str, str], warehouse_id: uuid.UUID, ct: uuid.UUID
) -> int:
    response = await client.get(
        f"/api/v1/inventory-locations/warehouse/{warehouse_id}/balance", headers=headers
    )
    assert response.status_code == 200, response.text
    return sum(
        line["quantity"]
        for line in response.json()["balances"]
        if line["cylinder_type_id"] == str(ct) and line["status"] == "filled"
    )


class TestStockCountNeedsASecondPerson:
    async def test_count_changes_stock_only_once_approved_by_someone_else(
        self, client: AsyncClient, admin_engine: AsyncEngine, integration_settings: Settings
    ) -> None:
        tenant_id, warehouse_id, ct = await _seed_tenant(admin_engine)
        counter = await _staff_token(
            client, admin_engine, integration_settings, tenant_id=tenant_id, role="warehouse_staff"
        )
        approver = await _staff_token(
            client, admin_engine, integration_settings, tenant_id=tenant_id, role="warehouse_staff"
        )

        grn = await client.post(
            f"/api/v1/warehouses/{warehouse_id}/goods-receipt-notes",
            json={"cylinder_type_id": str(ct), "quantity_received": 125},
            headers=counter,
        )
        assert grn.status_code == 201, grn.text

        count = await client.post(
            f"/api/v1/inventory-locations/warehouse/{warehouse_id}/reconciliation-records",
            json={"cylinder_type_id": str(ct), "status": "filled", "actual_quantity": 120},
            headers=counter,
        )
        assert count.status_code == 201, count.text
        record_id = count.json()["id"]
        assert count.json()["variance"] == -5
        # Recording alone moves nothing.
        assert await _filled(client, counter, warehouse_id, ct) == 125

        pending = await client.get(
            f"/api/v1/inventory-locations/warehouse/{warehouse_id}/reconciliation-records",
            params={"state": "pending"},
            headers=approver,
        )
        assert [r["id"] for r in pending.json()["items"]] == [record_id]

        own = await client.post(
            f"/api/v1/reconciliation-records/{record_id}/approve", headers=counter
        )
        assert own.status_code == 409, own.text
        assert own.json()["error_code"] == "SELF_APPROVAL_NOT_ALLOWED"
        assert await _filled(client, counter, warehouse_id, ct) == 125

        approved = await client.post(
            f"/api/v1/reconciliation-records/{record_id}/approve", headers=approver
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["state"] == "approved"
        assert await _filled(client, counter, warehouse_id, ct) == 120

        again = await client.post(
            f"/api/v1/reconciliation-records/{record_id}/approve", headers=approver
        )
        assert again.status_code == 409, again.text
        assert again.json()["error_code"] == "RECONCILIATION_ALREADY_DECIDED"
        assert await _filled(client, counter, warehouse_id, ct) == 120

    async def test_admin_can_approve_own_count(
        self, client: AsyncClient, admin_engine: AsyncEngine, integration_settings: Settings
    ) -> None:
        tenant_id, warehouse_id, ct = await _seed_tenant(admin_engine)
        admin = await _staff_token(
            client, admin_engine, integration_settings, tenant_id=tenant_id, role="agency_admin"
        )
        await client.post(
            f"/api/v1/warehouses/{warehouse_id}/goods-receipt-notes",
            json={"cylinder_type_id": str(ct), "quantity_received": 100},
            headers=admin,
        )
        count = await client.post(
            f"/api/v1/inventory-locations/warehouse/{warehouse_id}/reconciliation-records",
            json={"cylinder_type_id": str(ct), "status": "filled", "actual_quantity": 90},
            headers=admin,
        )
        assert count.status_code == 201, count.text
        record_id = count.json()["id"]

        approved = await client.post(
            f"/api/v1/reconciliation-records/{record_id}/approve", headers=admin
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["state"] == "approved"
        assert await _filled(client, admin, warehouse_id, ct) == 90

    async def test_reject_leaves_stock_and_closes_the_count(
        self, client: AsyncClient, admin_engine: AsyncEngine, integration_settings: Settings
    ) -> None:
        tenant_id, warehouse_id, ct = await _seed_tenant(admin_engine)
        counter = await _staff_token(
            client, admin_engine, integration_settings, tenant_id=tenant_id, role="warehouse_staff"
        )
        approver = await _staff_token(
            client, admin_engine, integration_settings, tenant_id=tenant_id, role="warehouse_staff"
        )
        await client.post(
            f"/api/v1/warehouses/{warehouse_id}/goods-receipt-notes",
            json={"cylinder_type_id": str(ct), "quantity_received": 10},
            headers=counter,
        )
        count = await client.post(
            f"/api/v1/inventory-locations/warehouse/{warehouse_id}/reconciliation-records",
            json={"cylinder_type_id": str(ct), "status": "filled", "actual_quantity": 4},
            headers=counter,
        )
        record_id = count.json()["id"]

        rejected = await client.post(
            f"/api/v1/reconciliation-records/{record_id}/reject",
            json={"reason": "Counted the wrong stack, recount"},
            headers=approver,
        )
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()["state"] == "rejected"
        assert await _filled(client, counter, warehouse_id, ct) == 10

        late_approve = await client.post(
            f"/api/v1/reconciliation-records/{record_id}/approve", headers=approver
        )
        assert late_approve.status_code == 409, late_approve.text

    async def test_another_tenant_cannot_decide_the_count(
        self, client: AsyncClient, admin_engine: AsyncEngine, integration_settings: Settings
    ) -> None:
        tenant_id, warehouse_id, ct = await _seed_tenant(admin_engine)
        other_tenant_id, _, _ = await _seed_tenant(admin_engine)
        counter = await _staff_token(
            client, admin_engine, integration_settings, tenant_id=tenant_id, role="agency_admin"
        )
        outsider = await _staff_token(
            client,
            admin_engine,
            integration_settings,
            tenant_id=other_tenant_id,
            role="warehouse_staff",
        )
        count = await client.post(
            f"/api/v1/inventory-locations/warehouse/{warehouse_id}/reconciliation-records",
            json={"cylinder_type_id": str(ct), "status": "filled", "actual_quantity": 3},
            headers=counter,
        )
        record_id = count.json()["id"]

        response = await client.post(
            f"/api/v1/reconciliation-records/{record_id}/approve", headers=outsider
        )
        assert response.status_code == 404, response.text
        listing = await client.get(
            f"/api/v1/inventory-locations/warehouse/{warehouse_id}/reconciliation-records",
            headers=outsider,
        )
        assert listing.json()["items"] == []


class TestGoodsReceiptAndOmcReturns:
    async def test_grn_documents_omc_return_and_stock_register(
        self, client: AsyncClient, admin_engine: AsyncEngine, integration_settings: Settings
    ) -> None:
        tenant_id, warehouse_id, ct = await _seed_tenant(admin_engine)
        headers = await _staff_token(
            client, admin_engine, integration_settings, tenant_id=tenant_id, role="agency_admin"
        )

        unknown = await client.post(
            f"/api/v1/warehouses/{warehouse_id}/goods-receipt-notes",
            json={"cylinder_type_id": str(ct), "quantity_received": 12, "source_omc": "Indane"},
            headers=headers,
        )
        assert unknown.status_code == 422, unknown.text

        grn = await client.post(
            f"/api/v1/warehouses/{warehouse_id}/goods-receipt-notes",
            json={
                "cylinder_type_id": str(ct),
                "quantity_received": 12,
                "source_omc": "iocl",
                "challan_number": "ch-4471",
                "invoice_number": "INV/26/0091",
                "truck_number": "ts09 ua 3320",
            },
            headers=headers,
        )
        assert grn.status_code == 201, grn.text
        body = grn.json()
        assert (body["source_omc"], body["challan_number"], body["truck_number"]) == (
            "iocl",
            "CH-4471",
            "TS09 UA 3320",
        )

        # Turn 5 filled into empties via the routine status cycle isn't
        # possible (empties come back from customers), so seed empties.
        async with admin_engine.begin() as conn:
            location_id = (
                await conn.execute(
                    text(
                        "SELECT id FROM inventory.inventory_location "
                        "WHERE location_ref_id = :wh AND location_type = 'warehouse'"
                    ),
                    {"wh": str(warehouse_id)},
                )
            ).scalar_one()
            await conn.execute(
                text(
                    "INSERT INTO inventory.inventory_balance "
                    "(id, tenant_id, inventory_location_id, cylinder_type_id, status, quantity) "
                    "VALUES (gen_random_uuid(), :t, :l, :ct, 'empty', 30)"
                ),
                {"t": str(tenant_id), "l": str(location_id), "ct": str(ct)},
            )

        too_many = await client.post(
            f"/api/v1/warehouses/{warehouse_id}/omc-returns",
            json={"cylinder_type_id": str(ct), "quantity": 31, "destination_omc": "iocl"},
            headers=headers,
        )
        assert too_many.status_code == 409, too_many.text
        assert too_many.json()["error_code"] == "INSUFFICIENT_STOCK"

        returned = await client.post(
            f"/api/v1/warehouses/{warehouse_id}/omc-returns",
            json={
                "cylinder_type_id": str(ct),
                "quantity": 25,
                "destination_omc": "iocl",
                "truck_number": "TS09UA3320",
            },
            headers=headers,
        )
        assert returned.status_code == 201, returned.text
        assert returned.json()["return_number"].startswith("ERN")

        today = datetime.now(UTC).astimezone(ZoneInfo("Asia/Kolkata")).date()
        register = await client.get(
            f"/api/v1/inventory-locations/warehouse/{warehouse_id}/stock-register",
            params={"date_from": today.isoformat(), "date_to": today.isoformat()},
            headers=headers,
        )
        assert register.status_code == 200, register.text
        lines = {line["status"]: line for line in register.json()["lines"]}
        assert (lines["filled"]["opening"], lines["filled"]["receipts"]) == (0, 12)
        assert lines["filled"]["closing"] == 12
        # The seeded 30 empties carry no ledger row, so they count as opening.
        assert (lines["empty"]["opening"], lines["empty"]["issues"]) == (30, 25)
        assert lines["empty"]["closing"] == 5

        transitions = await client.get("/api/v1/inventory/status-transitions", headers=headers)
        assert transitions.status_code == 200, transitions.text
        assert transitions.json()["status_change"]["filled"] == ["damaged", "leakage"]
