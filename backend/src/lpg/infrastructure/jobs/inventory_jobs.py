"""`check_reorder_levels` — daily inventory reorder-point alert cron (AI
Operational Intelligence, Horizon 1 Stage 4).

Per tenant: every currently-breached `(warehouse, cylinder_type)` — on-hand
`filled` quantity at or below its admin-set `reorder_point`
(`application/inventory/reorder.py`) — is recorded to `ai.prediction`
first, then enqueues one `inventory_low_stock_staff` notification, deduped
against `last_reorder_notified_at` so an overlapping/retried run doesn't
double-notify. No kill switch: this is a pure read + notify, the same
"not an irreversible action" reasoning `check_stale_unassigned_orders` and
`check_compliance_expiry` already use — the reorder-point thresholds
themselves are the tuning knob.

Cross-tenant iteration + per-tenant `RequestTenantContext` follows
`stale_order_jobs.py` / `feature_store_jobs.py` exactly.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog

from lpg.application.ai.prediction import RecordPredictionCommand, RecordPredictionUseCase
from lpg.application.common.tenant import RequestTenantContext
from lpg.application.inventory.reorder import (
    MODEL_VERSION,
    PREDICTION_TYPE,
    ListReorderSignalsQuery,
    ListReorderSignalsUseCase,
)
from lpg.config.logging import get_logger
from lpg.infrastructure.persistence.repositories.ai import SqlAlchemyPredictionRepository
from lpg.infrastructure.persistence.repositories.inventory import (
    SqlAlchemyReorderPolicyRepository,
)
from lpg.infrastructure.persistence.repositories.tenant import SqlAlchemyTenantRepository
from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

if TYPE_CHECKING:
    from lpg.infrastructure.jobs.pool import JobQueue
    from lpg.infrastructure.persistence.database import Database

_logger = get_logger(__name__)

#: Same cross-tenant, RLS-bypassing-read placeholder every other
#: all-tenant cron in this codebase duplicates rather than imports.
_CROSS_TENANT_PLACEHOLDER_ID = uuid.UUID(int=0)

#: A breach already notified more recently than this is skipped — guards
#: an overlapping/retried run against double-notifying, not against a
#: genuinely still-breached situation re-notifying on the next day's run.
NOTIFY_DEDUPE_HOURS = 20


async def check_reorder_levels_for_tenant(
    uow: SqlAlchemyUnitOfWork,
    job_queue: JobQueue,
    *,
    tenant_id: uuid.UUID,
) -> int:
    """Records every breach to `ai.prediction`, enqueues a notification for
    whichever ones aren't within their dedupe window, and marks those
    notified. Split out from the cron loop so it's testable against a
    single seeded tenant, the same reason every other Horizon 1 cron is.
    `uow` must already be tenant-scoped (RLS) for `tenant_id`. Returns the
    number of notifications actually enqueued."""
    reorder_policy_repo = SqlAlchemyReorderPolicyRepository(uow)
    prediction_repo = SqlAlchemyPredictionRepository(uow)

    signals = await ListReorderSignalsUseCase(reorder_policy_repo).execute(
        ListReorderSignalsQuery(tenant_id=tenant_id)
    )
    if not signals:
        return 0

    record_prediction = RecordPredictionUseCase(prediction_repo)
    now = datetime.now(UTC)
    notified = 0

    for signal in signals:
        await record_prediction.execute(
            RecordPredictionCommand(
                tenant_id=tenant_id,
                prediction_type=PREDICTION_TYPE,
                subject_type="inventory_location",
                subject_id=signal.inventory_location_id,
                model_version=MODEL_VERSION,
                value={
                    "cylinder_type_id": str(signal.cylinder_type_id),
                    "on_hand": signal.on_hand,
                    "reorder_point": signal.reorder_point,
                    "safety_stock": signal.safety_stock,
                },
            )
        )

        if signal.last_reorder_notified_at is not None and (
            now - signal.last_reorder_notified_at
        ) < timedelta(hours=NOTIFY_DEDUPE_HOURS):
            continue

        await job_queue.enqueue(
            "send_notification",
            {
                "type": "inventory_low_stock_staff",
                "tenant_id": str(tenant_id),
                "inventory_location_id": str(signal.inventory_location_id),
                "cylinder_type_id": str(signal.cylinder_type_id),
                "on_hand": str(signal.on_hand),
                "reorder_point": str(signal.reorder_point),
            },
            # ARQ's own dedupe primitive against overlapping runs the same
            # day — `last_reorder_notified_at` above is the real,
            # persistent dedupe; this only guards concurrent job attempts.
            _job_id=f"reorder_signal_{signal.policy_id}_{now.date().isoformat()}",
        )
        await reorder_policy_repo.mark_reorder_notified(signal.policy_id)
        notified += 1

    return notified


async def check_reorder_levels(ctx: dict[str, Any]) -> None:
    """Cron job: checks every tenant's reorder thresholds and notifies
    staff of new breaches.

    Per-tenant new session + O(all tenants) iteration — the same shape
    `check_stale_unassigned_orders` / `build_feature_snapshots` already
    use; fine for a real deployment's handful of tenants.
    """
    structlog.contextvars.bind_contextvars(
        correlation_id=str(uuid.uuid4()), job_name="check_reorder_levels"
    )
    database: Database = ctx["database"]
    job_queue: JobQueue = ctx["job_queue"]

    _logger.info("job_check_reorder_levels_started")

    async for session in database.open_session(tenant_id=None):
        cross_tenant_context = RequestTenantContext(tenant_id=_CROSS_TENANT_PLACEHOLDER_ID)
        async with SqlAlchemyUnitOfWork(session, cross_tenant_context) as uow:
            tenants = await SqlAlchemyTenantRepository(uow).list_all()

    total_notified = 0
    for tenant in tenants:
        if tenant.status == "closed":
            continue
        structlog.contextvars.bind_contextvars(tenant_id=str(tenant.id))
        async for session in database.open_session(tenant_id=tenant.id):
            tenant_context = RequestTenantContext(tenant_id=tenant.id)
            async with SqlAlchemyUnitOfWork(session, tenant_context) as uow:
                total_notified += await check_reorder_levels_for_tenant(
                    uow, job_queue, tenant_id=tenant.id
                )

    _logger.info("job_check_reorder_levels_completed", total_notified=total_notified)
