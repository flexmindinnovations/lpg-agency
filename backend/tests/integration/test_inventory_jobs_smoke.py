"""`check_reorder_levels_for_tenant` against a real Postgres + Redis — the
daily inventory reorder-point alert cron (AI Operational Intelligence,
Horizon 1 Stage 4).

What is real: a seeded tenant/warehouse/cylinder_type with a breached
`reorder_policy`, the job's own `ai.prediction` write, the notification
actually getting enqueued, and the `last_reorder_notified_at` dedupe gate
suppressing a second notification on a same-day re-run.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration

_ADMIN_URL = "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:5433/lpg_test"


async def _seed_breached_policy(engine: AsyncEngine) -> tuple[uuid.UUID, uuid.UUID]:
    """tenant -> warehouse -> inventory_location -> cylinder_type with a
    low `inventory_balance` row and a `reorder_policy` it breaches. Returns
    `(tenant_id, policy_id)`."""
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'Reorder Job Smoke', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"reorder-job-smoke-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
        branch_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.branch (id, tenant_id, name) "
                    "VALUES (gen_random_uuid(), :t, 'Reorder Job Smoke Branch') RETURNING id"
                ),
                {"t": str(tenant_id)},
            )
        ).scalar_one()
        warehouse_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.warehouse (id, tenant_id, branch_id, name, address_line) "
                    "VALUES (gen_random_uuid(), :t, :b, 'Reorder Job Smoke WH', '1 Depot Rd') "
                    "RETURNING id"
                ),
                {"t": str(tenant_id), "b": str(branch_id)},
            )
        ).scalar_one()
        location_id = (
            await conn.execute(
                text(
                    "INSERT INTO inventory.inventory_location "
                    "(id, tenant_id, location_type, location_ref_id) "
                    "VALUES (gen_random_uuid(), :t, 'warehouse', :w) RETURNING id"
                ),
                {"t": str(tenant_id), "w": str(warehouse_id)},
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
        await conn.execute(
            text(
                "INSERT INTO inventory.inventory_balance "
                "(id, tenant_id, inventory_location_id, cylinder_type_id, status, quantity) "
                "VALUES (gen_random_uuid(), :t, :loc, :ct, 'filled', 3)"
            ),
            {"t": str(tenant_id), "loc": str(location_id), "ct": str(cylinder_type_id)},
        )
        policy_id = (
            await conn.execute(
                text(
                    "INSERT INTO inventory.reorder_policy "
                    "(id, tenant_id, inventory_location_id, cylinder_type_id, reorder_point, "
                    "safety_stock) "
                    "VALUES (gen_random_uuid(), :t, :loc, :ct, 10, 0) RETURNING id"
                ),
                {"t": str(tenant_id), "loc": str(location_id), "ct": str(cylinder_type_id)},
            )
        ).scalar_one()
    return (uuid.UUID(str(tenant_id)), uuid.UUID(str(policy_id)))


async def _run_check(integration_settings: Settings, tenant_id: uuid.UUID) -> int:
    from lpg.application.common.tenant import RequestTenantContext
    from lpg.infrastructure.jobs.inventory_jobs import check_reorder_levels_for_tenant
    from lpg.infrastructure.jobs.pool import JobQueue
    from lpg.infrastructure.persistence.database import build_database
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    database = build_database(integration_settings)
    database.connect()
    job_queue = JobQueue(integration_settings)
    await job_queue.connect()
    try:
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(
                session, RequestTenantContext(tenant_id=tenant_id)
            ) as uow:
                return await check_reorder_levels_for_tenant(uow, job_queue, tenant_id=tenant_id)
        return 0
    finally:
        await database.disconnect()
        await job_queue.disconnect()


async def test_check_reorder_levels_notifies_once_then_dedupes(
    integration_settings: Settings, postgres_available: bool
) -> None:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable")

    engine = create_async_engine(_ADMIN_URL)
    try:
        tenant_id, policy_id = await _seed_breached_policy(engine)

        notified = await _run_check(integration_settings, tenant_id)
        assert notified == 1

        async with engine.begin() as conn:
            prediction_count = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM ai.prediction "
                        "WHERE tenant_id = :t AND prediction_type = 'reorder_signal'"
                    ),
                    {"t": str(tenant_id)},
                )
            ).scalar_one()
            notified_at = (
                await conn.execute(
                    text(
                        "SELECT last_reorder_notified_at FROM inventory.reorder_policy "
                        "WHERE id = :p"
                    ),
                    {"p": str(policy_id)},
                )
            ).scalar_one()

        assert prediction_count == 1
        assert notified_at is not None

        # Same-day re-run: a fresh ai.prediction row is still written (the
        # traceable read model refreshes every run), but the dedupe gate
        # suppresses a second notification.
        notified_again = await _run_check(integration_settings, tenant_id)
        assert notified_again == 0

        async with engine.begin() as conn:
            prediction_count_after = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM ai.prediction "
                        "WHERE tenant_id = :t AND prediction_type = 'reorder_signal'"
                    ),
                    {"t": str(tenant_id)},
                )
            ).scalar_one()
        assert prediction_count_after == 2

        async with engine.begin() as conn:
            for stmt in (
                "DELETE FROM ai.prediction WHERE tenant_id = :t",
                "DELETE FROM inventory.reorder_policy WHERE tenant_id = :t",
                "DELETE FROM inventory.inventory_balance WHERE tenant_id = :t",
                "DELETE FROM inventory.inventory_location WHERE tenant_id = :t",
                "DELETE FROM tenant.cylinder_type WHERE tenant_id = :t",
                "DELETE FROM tenant.warehouse WHERE tenant_id = :t",
                "DELETE FROM tenant.branch WHERE tenant_id = :t",
                "DELETE FROM tenant.tenant WHERE id = :t",
            ):
                await conn.execute(text(stmt), {"t": str(tenant_id)})
    finally:
        await engine.dispose()
