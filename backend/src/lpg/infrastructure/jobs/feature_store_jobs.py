"""`build_feature_snapshots` — nightly point-in-time feature store build.

Runs before `refresh_materialized_views` (01:30 vs 02:00) so it reads the
*previous* day's settled MVs, not a mid-refresh state. Per tenant, per
`as_of_date` (today, UTC), computes one `ai.feature_snapshot` row per
entity and bulk-inserts them with `ON CONFLICT DO NOTHING` — a retried or
re-run job for the same day is a no-op.

Cross-tenant iteration + per-tenant `RequestTenantContext` follows
`stale_order_jobs.py` exactly. Reads are RLS-scoped by the per-tenant
session; the one exception is `rpt.mv_customer_consumption`, a
materialized view (no RLS possible), which is filtered by `tenant_id`
explicitly.

Horizon 1 writes one entity family — `customer_refill`, what
`PredictRefillDueUseCase` (Stage 2) consumes. `branch_cylinder_demand` and
`route_stop_duration` are follow-up commits of this same stage.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
import structlog

from lpg.application.ai.feature_store import ENTITY_CUSTOMER_REFILL, FeatureSnapshot
from lpg.application.common.tenant import RequestTenantContext
from lpg.config.logging import get_logger
from lpg.infrastructure.persistence.repositories.ai import SqlAlchemyFeatureSnapshotRepository
from lpg.infrastructure.persistence.repositories.tenant import SqlAlchemyTenantRepository
from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

if TYPE_CHECKING:
    from datetime import date

    from lpg.infrastructure.persistence.database import Database

_logger = get_logger(__name__)

#: RLS-bypassing-read placeholder for the cross-tenant tenant list —
#: same as `stale_order_jobs.py` / `compliance_jobs.py`.
_CROSS_TENANT_PLACEHOLDER_ID = uuid.UUID(int=0)

#: Per-customer refill features. `mv_customer_consumption` supplies the
#: interval (already computed from the cylinder ledger); everything else
#: comes from the order tables. One row per customer with ≥1 delivered
#: order.
_CUSTOMER_REFILL_SQL = sa.text("""
    WITH delivered AS (
        SELECT
            o.customer_id,
            o.branch_id,
            osh.changed_at,
            row_number() OVER (
                PARTITION BY o.customer_id ORDER BY osh.changed_at DESC
            ) AS rn
        FROM orders."order" o
        JOIN orders.order_status_history osh
            ON osh.order_id = o.id AND osh.to_status = 'delivered'
    ),
    agg AS (
        SELECT
            customer_id,
            max(changed_at) AS last_delivered_at,
            count(*) AS delivery_count
        FROM delivered
        GROUP BY customer_id
    ),
    last_branch AS (
        SELECT customer_id, branch_id FROM delivered WHERE rn = 1
    ),
    primary_ct AS (
        SELECT DISTINCT ON (o.customer_id)
            o.customer_id,
            ol.cylinder_type_id
        FROM orders."order" o
        JOIN orders.order_line ol ON ol.order_id = o.id
        GROUP BY o.customer_id, ol.cylinder_type_id
        ORDER BY o.customer_id, sum(ol.quantity_ordered) DESC
    )
    SELECT
        a.customer_id,
        a.last_delivered_at,
        a.delivery_count,
        lb.branch_id,
        pc.cylinder_type_id AS primary_cylinder_type_id,
        mc.avg_refill_interval_days
    FROM agg a
    LEFT JOIN last_branch lb ON lb.customer_id = a.customer_id
    LEFT JOIN primary_ct pc ON pc.customer_id = a.customer_id
    LEFT JOIN rpt.mv_customer_consumption mc
        ON mc.customer_id = a.customer_id AND mc.tenant_id = :tenant_id
""")


async def build_customer_refill_snapshots_for_tenant(
    uow: SqlAlchemyUnitOfWork,
    *,
    tenant_id: uuid.UUID,
    as_of_date: date,
) -> int:
    """Compute + persist this tenant's `customer_refill` snapshots for one
    date. Split out from the cron loop so it's testable against a single
    seeded tenant without iterating every tenant in the database. `uow`
    must already be tenant-scoped (RLS) for `tenant_id`. Returns the number
    of rows actually inserted (`ON CONFLICT DO NOTHING` skips a re-run)."""
    repo = SqlAlchemyFeatureSnapshotRepository(uow)
    rows = (
        await uow.session.execute(_CUSTOMER_REFILL_SQL, {"tenant_id": str(tenant_id)})
    ).mappings()

    snapshots: list[FeatureSnapshot] = []
    for row in rows:
        last_delivered_at: datetime | None = row["last_delivered_at"]
        days_since_last = (
            (as_of_date - last_delivered_at.date()).days
            if last_delivered_at is not None
            else None
        )
        interval = row["avg_refill_interval_days"]
        snapshots.append(
            FeatureSnapshot(
                id=repo.next_id(),
                tenant_id=tenant_id,
                entity_type=ENTITY_CUSTOMER_REFILL,
                entity_id=row["customer_id"],
                as_of_date=as_of_date,
                features={
                    "last_delivered_at": last_delivered_at.isoformat()
                    if last_delivered_at is not None
                    else None,
                    "days_since_last": days_since_last,
                    "delivery_count": int(row["delivery_count"]),
                    "avg_refill_interval_days": float(interval) if interval is not None else None,
                    "branch_id": str(row["branch_id"]) if row["branch_id"] is not None else None,
                    "primary_cylinder_type_id": str(row["primary_cylinder_type_id"])
                    if row["primary_cylinder_type_id"] is not None
                    else None,
                },
            )
        )

    written = await repo.add_ignoring_conflicts(snapshots)
    _logger.info(
        "feature_snapshots_written",
        entity_type=ENTITY_CUSTOMER_REFILL,
        computed=len(snapshots),
        inserted=written,
    )
    return written


async def build_feature_snapshots(ctx: dict[str, Any]) -> None:
    """Cron job: writes today's `ai.feature_snapshot` rows for every tenant.

    Per-tenant new session + O(all tenants) iteration — the same shape
    `check_stale_unassigned_orders` / `check_compliance_expiry` already use;
    fine for a real deployment's handful of tenants, slow only against a
    test database with tens of thousands of leftover tenants.
    """
    structlog.contextvars.bind_contextvars(
        correlation_id=str(uuid.uuid4()), job_name="build_feature_snapshots"
    )
    database: Database = ctx["database"]
    as_of_date = datetime.now(UTC).date()

    _logger.info("job_build_feature_snapshots_started", as_of_date=as_of_date.isoformat())

    async for session in database.open_session(tenant_id=None):
        cross_tenant_context = RequestTenantContext(tenant_id=_CROSS_TENANT_PLACEHOLDER_ID)
        async with SqlAlchemyUnitOfWork(session, cross_tenant_context) as uow:
            tenants = await SqlAlchemyTenantRepository(uow).list_all()

    total_written = 0
    for tenant in tenants:
        if tenant.status == "closed":
            continue
        structlog.contextvars.bind_contextvars(tenant_id=str(tenant.id))
        async for session in database.open_session(tenant_id=tenant.id):
            tenant_context = RequestTenantContext(tenant_id=tenant.id)
            async with SqlAlchemyUnitOfWork(session, tenant_context) as uow:
                total_written += await build_customer_refill_snapshots_for_tenant(
                    uow, tenant_id=tenant.id, as_of_date=as_of_date
                )

    _logger.info(
        "job_build_feature_snapshots_completed",
        as_of_date=as_of_date.isoformat(),
        total_written=total_written,
    )
