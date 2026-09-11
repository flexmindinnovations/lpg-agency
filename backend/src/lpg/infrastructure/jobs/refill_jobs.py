"""`predict_refill_due` — daily refill-due prediction + proactive nudge
cron (AI Operational Intelligence, Horizon 1 Stage 2).

Per tenant: reads every customer's latest `customer_refill` feature
snapshot (`ai.feature_snapshot`, written the night before by
`feature_store_jobs.build_feature_snapshots`), computes today's refill-due
prediction for each via `PredictRefillDueUseCase` (always — this is the
traceable read model `GET /customers/refill-due` serves, independent of
whether nudging is on), and — only when the tenant has opted into
`refill_nudge_enabled` — enqueues a `refill_due_customer` notification for
whoever is due within the configured lead window and past the configured
minimum gap since their last delivery.

Cross-tenant iteration + per-tenant `RequestTenantContext` follows
`stale_order_jobs.py` exactly. Runs after `build_feature_snapshots`
(01:30) so today's snapshots already exist.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from lpg.application.ai.feature_store import ENTITY_CUSTOMER_REFILL
from lpg.application.common.config import is_truthy_config_value
from lpg.application.common.tenant import RequestTenantContext
from lpg.application.customer.refill_prediction import (
    PredictRefillDueForCustomerCommand,
    PredictRefillDueUseCase,
)
from lpg.application.tenant.tenant_configuration import (
    GetEffectiveTenantConfigurationQuery,
    GetEffectiveTenantConfigurationUseCase,
)
from lpg.config.logging import get_logger
from lpg.infrastructure.persistence.repositories.ai import (
    SqlAlchemyFeatureSnapshotRepository,
    SqlAlchemyPredictionRepository,
)
from lpg.infrastructure.persistence.repositories.customer import SqlAlchemyCustomerRepository
from lpg.infrastructure.persistence.repositories.tenant import (
    SqlAlchemyTenantConfigurationRepository,
    SqlAlchemyTenantRepository,
)
from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

if TYPE_CHECKING:
    from datetime import date

    from lpg.application.customer.ports import FieldEncryptor
    from lpg.application.tenant.ports import TenantConfigurationRepository
    from lpg.infrastructure.jobs.pool import JobQueue
    from lpg.infrastructure.persistence.database import Database

_logger = get_logger(__name__)

#: Same cross-tenant, RLS-bypassing-read placeholder every other
#: all-tenant cron in this codebase duplicates rather than imports
#: (`stale_order_jobs.py` / `feature_store_jobs.py`'s own copies).
_CROSS_TENANT_PLACEHOLDER_ID = uuid.UUID(int=0)

#: Applied when a tenant has no `refill_nudge_lead_days` configuration
#: entry of its own — nudge a customer once their predicted refill date is
#: within this many days.
DEFAULT_LEAD_DAYS = 3

#: Applied when a tenant has no `refill_nudge_min_gap_days` entry — never
#: nudge a customer whose last delivery was more recent than this, even if
#: a noisy/short blended interval says they're already due. Not an
#: enforced order-placement rule elsewhere in this codebase (there isn't
#: one) — purely this nudge's own sanity floor against a fluke-short
#: estimate.
DEFAULT_MIN_GAP_DAYS = 5


async def predict_refill_due_for_tenant(
    uow: SqlAlchemyUnitOfWork,
    job_queue: JobQueue,
    field_encryptor: FieldEncryptor,
    *,
    tenant_id: uuid.UUID,
    as_of: date,
) -> tuple[int, int]:
    """Computes + records today's `refill_due` prediction for every
    customer this tenant has a `customer_refill` feature snapshot for, and
    — only where `refill_nudge_enabled` — enqueues a notification for
    whoever is due soon and past the minimum gap since their last
    delivery. Split out from the cron loop so it's testable against a
    single seeded tenant, the same reason `feature_store_jobs.
    build_customer_refill_snapshots_for_tenant` exists. `uow` must already
    be tenant-scoped (RLS) for `tenant_id`. Returns
    `(predictions_written, nudges_sent)`."""
    feature_repo = SqlAlchemyFeatureSnapshotRepository(uow)
    prediction_repo = SqlAlchemyPredictionRepository(uow)
    customer_repo = SqlAlchemyCustomerRepository(uow, field_encryptor)
    config_repo = SqlAlchemyTenantConfigurationRepository(uow)

    snapshots = await feature_repo.list_latest_by_entity_type(entity_type=ENTITY_CUSTOMER_REFILL)
    if not snapshots:
        return (0, 0)

    known_intervals = [
        float(s.features["avg_refill_interval_days"])
        for s in snapshots
        if s.features.get("avg_refill_interval_days") is not None
    ]
    population_mean = sum(known_intervals) / len(known_intervals) if known_intervals else None

    nudge_enabled = await _is_enabled(config_repo, tenant_id, "refill_nudge_enabled")
    lead_days = await _get_int_config(
        config_repo, tenant_id, "refill_nudge_lead_days", DEFAULT_LEAD_DAYS
    )
    min_gap_days = await _get_int_config(
        config_repo, tenant_id, "refill_nudge_min_gap_days", DEFAULT_MIN_GAP_DAYS
    )

    use_case = PredictRefillDueUseCase(feature_repo, prediction_repo)
    predictions_written = 0
    nudges_sent = 0
    for snapshot in snapshots:
        prediction = await use_case.execute(
            PredictRefillDueForCustomerCommand(
                tenant_id=tenant_id,
                customer_id=snapshot.entity_id,
                as_of=as_of,
                population_mean_interval_days=population_mean,
            )
        )
        if prediction is None:
            continue
        predictions_written += 1

        if not nudge_enabled:
            continue
        days_until_due = (prediction.refill_due_date - as_of).days
        if days_until_due > lead_days:
            continue
        days_since_last = (as_of - prediction.last_delivered_at).days
        if days_since_last < min_gap_days:
            continue
        last_nudge = await customer_repo.get_last_refill_nudge_sent_at(snapshot.entity_id)
        if last_nudge is not None and (datetime.now(UTC) - last_nudge).days < lead_days:
            # Already nudged for this same due cycle — the dedupe
            # `last_refill_nudge_sent_at` gate, the same shape as
            # `OrderRepository.mark_stale_notified`.
            continue

        await job_queue.enqueue(
            "send_notification",
            {
                "type": "refill_due_customer",
                "tenant_id": str(tenant_id),
                "customer_id": str(snapshot.entity_id),
                "refill_due_date": prediction.refill_due_date.isoformat(),
            },
            # ARQ's own dedupe primitive against overlapping runs for the
            # same customer + due date.
            _job_id=f"refill_due_{snapshot.entity_id}_{prediction.refill_due_date.isoformat()}",
        )
        await customer_repo.mark_refill_nudge_sent(snapshot.entity_id)
        nudges_sent += 1

    return (predictions_written, nudges_sent)


async def predict_refill_due(ctx: dict[str, Any]) -> None:
    """Cron job: writes today's `refill_due` prediction for every customer
    with a feature snapshot, and — where `refill_nudge_enabled` — nudges
    whoever is due soon and past the minimum gap since their last order.

    Per-tenant new session + O(all tenants) iteration — the same shape
    `check_stale_unassigned_orders` / `build_feature_snapshots` already
    use; fine for a real deployment's handful of tenants.
    """
    structlog.contextvars.bind_contextvars(
        correlation_id=str(uuid.uuid4()), job_name="predict_refill_due"
    )
    database: Database = ctx["database"]
    job_queue: JobQueue = ctx["job_queue"]
    today = datetime.now(UTC).date()

    _logger.info("job_predict_refill_due_started", as_of=today.isoformat())

    async for session in database.open_session(tenant_id=None):
        cross_tenant_context = RequestTenantContext(tenant_id=_CROSS_TENANT_PLACEHOLDER_ID)
        async with SqlAlchemyUnitOfWork(session, cross_tenant_context) as uow:
            tenants = await SqlAlchemyTenantRepository(uow).list_all()

    from lpg.config.settings import get_settings
    from lpg.infrastructure.security.field_encryption import FernetFieldEncryptor

    field_encryptor = FernetFieldEncryptor(get_settings())

    total_predictions = 0
    total_nudges = 0
    for tenant in tenants:
        if tenant.status == "closed":
            continue
        structlog.contextvars.bind_contextvars(tenant_id=str(tenant.id))
        async for session in database.open_session(tenant_id=tenant.id):
            tenant_context = RequestTenantContext(tenant_id=tenant.id)
            async with SqlAlchemyUnitOfWork(session, tenant_context) as uow:
                written, sent = await predict_refill_due_for_tenant(
                    uow, job_queue, field_encryptor, tenant_id=tenant.id, as_of=today
                )
                total_predictions += written
                total_nudges += sent

    _logger.info(
        "job_predict_refill_due_completed",
        as_of=today.isoformat(),
        predictions_written=total_predictions,
        nudges_sent=total_nudges,
    )


async def _is_enabled(
    config_repo: TenantConfigurationRepository, tenant_id: uuid.UUID, key: str
) -> bool:
    config = await GetEffectiveTenantConfigurationUseCase(config_repo).execute(
        GetEffectiveTenantConfigurationQuery(tenant_id=tenant_id, config_key=key)
    )
    return config is not None and is_truthy_config_value(config.config_value)


async def _get_int_config(
    config_repo: TenantConfigurationRepository, tenant_id: uuid.UUID, key: str, default: int
) -> int:
    config = await GetEffectiveTenantConfigurationUseCase(config_repo).execute(
        GetEffectiveTenantConfigurationQuery(tenant_id=tenant_id, config_key=key)
    )
    if config is None:
        return default
    try:
        return int(config.config_value)
    except (TypeError, ValueError):
        _logger.warning("refill_nudge_config_invalid", key=key, value=config.config_value)
        return default
