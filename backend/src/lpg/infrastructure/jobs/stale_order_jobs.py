"""Stale-unassigned-order alert — hourly cron (order-to-delivery
fulfillment automation, ADR-046's own survey of other automatable
processes; recommended as the safest first follow-up).

Iterates every tenant, resolves that tenant's configured staleness
threshold (default `DEFAULT_STALE_HOURS`) via `TenantConfiguration` key
`stale_unassigned_order_hours`, and enqueues one
`order_stale_unassigned_staff` notification per order
`OrderRepository.list_stale_unassigned()` returns — that repository
method itself excludes orders already notified within the same window
(`last_stale_notified_at`), so a re-run (retry, or the next hourly tick
before staff act) never double-notifies; this job additionally marks
each order notified before moving to the next, the exact same
read-then-mark-then-commit shape `check_compliance_expiry` already uses
for the identical problem on `ComplianceDocument`.

Pure read + notify — no mutation, no kill switch (unlike the auto-
assignment feature this survey came from, a notification is not an
irreversible action, and the closest precedent, `check_compliance_
expiry`, has no kill switch either); `stale_unassigned_order_hours` is a
tuning knob, not an on/off gate.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import structlog

from lpg.config.logging import get_logger

if TYPE_CHECKING:
    from lpg.infrastructure.jobs.pool import JobQueue
    from lpg.infrastructure.persistence.database import Database

_logger = get_logger(__name__)

#: Threshold applied when a tenant has no `stale_unassigned_order_hours`
#: configuration entry of its own.
DEFAULT_STALE_HOURS = 4

#: Same cross-tenant, RLS-bypassing-read placeholder `check_compliance_
#: expiry` uses for the identical situation (`SqlAlchemyTenantRepository.
#: list_all()`), duplicated rather than imported to keep this module
#: independent — same self-containment reasoning as that module's own copy.
_CROSS_TENANT_PLACEHOLDER_ID = uuid.UUID(int=0)


async def check_stale_unassigned_orders(ctx: dict[str, Any]) -> None:
    """Cron job: flags every order still `confirmed` (unassigned, by
    construction) past its tenant's configured staleness threshold and
    enqueues an `order_stale_unassigned_staff` notification for each."""
    structlog.contextvars.bind_contextvars(
        correlation_id=str(uuid.uuid4()), job_name="check_stale_unassigned_orders"
    )
    database: Database = ctx["database"]
    job_queue: JobQueue = ctx["job_queue"]

    _logger.info("job_check_stale_unassigned_orders_started")

    from lpg.application.common.tenant import RequestTenantContext
    from lpg.application.tenant.tenant_configuration import (
        GetEffectiveTenantConfigurationQuery,
        GetEffectiveTenantConfigurationUseCase,
    )
    from lpg.infrastructure.persistence.repositories.order import SqlAlchemyOrderRepository
    from lpg.infrastructure.persistence.repositories.tenant import (
        SqlAlchemyTenantConfigurationRepository,
        SqlAlchemyTenantRepository,
    )
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    async for session in database.open_session(tenant_id=None):
        cross_tenant_context = RequestTenantContext(tenant_id=_CROSS_TENANT_PLACEHOLDER_ID)
        async with SqlAlchemyUnitOfWork(session, cross_tenant_context) as uow:
            tenants = await SqlAlchemyTenantRepository(uow).list_all()

    orders_notified = 0
    for tenant in tenants:
        if tenant.status == "closed":
            continue

        structlog.contextvars.bind_contextvars(tenant_id=str(tenant.id))
        async for session in database.open_session(tenant_id=tenant.id):
            tenant_context = RequestTenantContext(tenant_id=tenant.id)
            async with SqlAlchemyUnitOfWork(session, tenant_context) as uow:
                config_repo = SqlAlchemyTenantConfigurationRepository(uow)
                stale_hours = DEFAULT_STALE_HOURS
                config = await GetEffectiveTenantConfigurationUseCase(config_repo).execute(
                    GetEffectiveTenantConfigurationQuery(
                        tenant_id=tenant.id, config_key="stale_unassigned_order_hours"
                    )
                )
                if config is not None:
                    try:
                        stale_hours = int(config.config_value)
                    except (TypeError, ValueError):
                        _logger.warning(
                            "stale_unassigned_order_hours_invalid", value=config.config_value
                        )

                order_repository = SqlAlchemyOrderRepository(uow)
                stale_orders = await order_repository.list_stale_unassigned(
                    timedelta(hours=stale_hours)
                )

                for order in stale_orders:
                    await job_queue.enqueue(
                        "send_notification",
                        {
                            "type": "order_stale_unassigned_staff",
                            "tenant_id": str(tenant.id),
                            "order_id": str(order.id),
                        },
                        # Deterministic id -- ARQ's own dedupe primitive
                        # (`check_compliance_expiry`'s own docstring) -- a
                        # retried or overlapping cron run enqueues the same
                        # notification job at most once per order per hour.
                        _job_id=f"stale_unassigned_{order.id}",
                    )
                    await order_repository.mark_stale_notified(order.id)
                    orders_notified += 1

    _logger.info("job_check_stale_unassigned_orders_completed", orders_notified=orders_notified)
