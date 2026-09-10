"""`build_feature_snapshots` against a real Postgres session — the nightly
point-in-time feature-store build (AI Operational Intelligence, Horizon 1
Stage 1a).

Cron job: called directly with a plain `ctx` dict, the same shape ARQ
hands it. What is real — a seeded delivered order graph, the job's own
cross-schema SQL against it, and the `ai.feature_snapshot` rows it writes,
including the `ON CONFLICT DO NOTHING` idempotency on a second run.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from lpg.application.ai.feature_store import ENTITY_CUSTOMER_REFILL

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration

_ADMIN_URL = "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:5433/lpg_test"


async def _seed_delivered_order(
    engine: AsyncEngine, *, delivered_days_ago: int
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Minimal graph: tenant → branch → customer → address → cylinder type →
    order (+ line) → an `order_status_history` row `-> delivered`.
    Returns (tenant_id, customer_id, cylinder_type_id)."""
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'FS Smoke', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"fs-smoke-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
        branch_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.branch (id, tenant_id, name) "
                    "VALUES (gen_random_uuid(), :t, 'FS Smoke Branch') RETURNING id"
                ),
                {"t": str(tenant_id)},
            )
        ).scalar_one()
        cylinder_type_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.cylinder_type (id, tenant_id, name, weight_kg) "
                    "VALUES (gen_random_uuid(), :t, '14.2kg Domestic', 14.2) RETURNING id"
                ),
                {"t": str(tenant_id)},
            )
        ).scalar_one()
        customer_id = (
            await conn.execute(
                text(
                    "INSERT INTO customer.customer "
                    "(id, tenant_id, branch_id, customer_type, full_name, phone_number, "
                    "consumer_number) "
                    "VALUES (gen_random_uuid(), :t, :b, 'domestic', 'FS Smoke Customer', "
                    ":phone, :cn) RETURNING id"
                ),
                {
                    "t": str(tenant_id),
                    "b": str(branch_id),
                    "phone": f"9{uuid.uuid4().int % 10**9:09d}",
                    "cn": f"CN-{uuid.uuid4().hex[:8]}",
                },
            )
        ).scalar_one()
        address_id = (
            await conn.execute(
                text(
                    "INSERT INTO customer.customer_address (id, tenant_id, customer_id, line_1) "
                    "VALUES (gen_random_uuid(), :t, :c, '1 FS Rd') RETURNING id"
                ),
                {"t": str(tenant_id), "c": str(customer_id)},
            )
        ).scalar_one()
        order_id = (
            await conn.execute(
                text(
                    "INSERT INTO orders.order "
                    "(id, tenant_id, branch_id, customer_id, address_id, delivery_address_line, "
                    "status, booking_source, requested_date) "
                    "VALUES (gen_random_uuid(), :t, :b, :c, :a, '1 FS Rd', 'delivered', 'staff', "
                    "now()) RETURNING id"
                ),
                {
                    "t": str(tenant_id),
                    "b": str(branch_id),
                    "c": str(customer_id),
                    "a": str(address_id),
                },
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO orders.order_line "
                "(id, order_id, cylinder_type_id, quantity_ordered) "
                "VALUES (gen_random_uuid(), :o, :ct, 2)"
            ),
            {"o": str(order_id), "ct": str(cylinder_type_id)},
        )
        await conn.execute(
            text(
                "INSERT INTO orders.order_status_history "
                "(id, order_id, from_status, to_status, changed_by, changed_at) "
                "VALUES (gen_random_uuid(), :o, 'out_for_delivery', 'delivered', "
                "gen_random_uuid(), :when)"
            ),
            {"o": str(order_id), "when": datetime.now(UTC) - timedelta(days=delivered_days_ago)},
        )
    return (
        uuid.UUID(str(tenant_id)),
        uuid.UUID(str(customer_id)),
        uuid.UUID(str(cylinder_type_id)),
    )


async def _run_build_for_tenant(integration_settings: Settings, tenant_id: uuid.UUID) -> int:
    """Runs the per-tenant snapshot build directly (not the cron's
    all-tenants loop — `lpg_test` has tens of thousands of leftover
    tenants). Exercises the same SQL, shaping, and `ON CONFLICT` path the
    cron does per tenant."""
    from lpg.application.common.tenant import RequestTenantContext
    from lpg.infrastructure.jobs.feature_store_jobs import (
        build_customer_refill_snapshots_for_tenant,
    )
    from lpg.infrastructure.persistence.database import build_database
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    database = build_database(integration_settings)
    database.connect()
    try:
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(
                session, RequestTenantContext(tenant_id=tenant_id)
            ) as uow:
                return await build_customer_refill_snapshots_for_tenant(
                    uow, tenant_id=tenant_id, as_of_date=datetime.now(UTC).date()
                )
        return 0
    finally:
        await database.disconnect()


async def test_build_writes_a_customer_refill_snapshot(
    integration_settings: Settings, postgres_available: bool
) -> None:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable")

    engine = create_async_engine(_ADMIN_URL)
    try:
        tenant_id, customer_id, cylinder_type_id = await _seed_delivered_order(
            engine, delivered_days_ago=20
        )

        written = await _run_build_for_tenant(integration_settings, tenant_id)
        assert written == 1

        async with engine.begin() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT entity_type, entity_id, as_of_date, features "
                        "FROM ai.feature_snapshot "
                        "WHERE tenant_id = :t AND entity_id = :c"
                    ),
                    {"t": str(tenant_id), "c": str(customer_id)},
                )
            ).mappings().all()

        assert len(rows) == 1
        snap = rows[0]
        assert snap["entity_type"] == ENTITY_CUSTOMER_REFILL
        assert snap["as_of_date"] == datetime.now(UTC).date()
        feats = snap["features"]
        assert feats["delivery_count"] == 1
        assert feats["days_since_last"] == 20
        assert feats["primary_cylinder_type_id"] == str(cylinder_type_id)
        assert feats["last_delivered_at"] is not None

        # Second run is a no-op — ON CONFLICT DO NOTHING on the day's row.
        rerun_written = await _run_build_for_tenant(integration_settings, tenant_id)
        assert rerun_written == 0
        async with engine.begin() as conn:
            count = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM ai.feature_snapshot "
                        "WHERE tenant_id = :t AND entity_id = :c"
                    ),
                    {"t": str(tenant_id), "c": str(customer_id)},
                )
            ).scalar_one()
        assert count == 1

        # Cleanup — this test seeds its own tenant. Delete children first:
        # branch/cylinder_type FKs to tenant have no ON DELETE CASCADE,
        # but customer/order/etc do cascade off branch.
        async with engine.begin() as conn:
            for stmt in (
                "DELETE FROM ai.feature_snapshot WHERE tenant_id = :t",
                "DELETE FROM ai.prediction WHERE tenant_id = :t",
                "DELETE FROM tenant.branch WHERE tenant_id = :t",
                "DELETE FROM tenant.cylinder_type WHERE tenant_id = :t",
                "DELETE FROM tenant.tenant WHERE id = :t",
            ):
                await conn.execute(text(stmt), {"t": str(tenant_id)})
    finally:
        await engine.dispose()
