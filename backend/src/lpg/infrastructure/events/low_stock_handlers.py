"""Low-stock alerts the moment stock drops, not only at the 07:00 cron.

After a van is loaded from the godown (the day's big stock movement), the tenant's
reorder points are re-checked (`inventory_jobs.check_reorder_levels_for_
tenant`, the same rule and the same 20-hour per-policy dedupe the daily cron
uses) and any new breach goes to the staff who can reorder
(`inventory:adjust`) through the in-app-first notifier.

Opens its own session, like `accounting_handlers`, and never raises: a
failed check must not fail the load or adjustment that triggered it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from lpg.domain.delivery.route import VehicleLoaded

if TYPE_CHECKING:
    import uuid

    from lpg.domain.common.base import DomainEvent
    from lpg.infrastructure.events.dispatcher import DomainEventDispatcher
    from lpg.infrastructure.notification.delivery import Notifier
    from lpg.infrastructure.persistence.database import Database

_logger = structlog.get_logger(__name__)


def register_low_stock_handlers(
    dispatcher: DomainEventDispatcher, database: Database, notifier: Notifier
) -> None:
    async def _check(event: DomainEvent) -> None:
        tenant_id: uuid.UUID | None = getattr(event, "tenant_id", None)
        if tenant_id is None:
            return
        try:
            payloads = await _collect_breaches(database, tenant_id)
        except Exception:
            _logger.exception("low_stock_check_failed", tenant_id=str(tenant_id))
            return
        for payload in payloads:
            await notifier.notify(payload)

    # `InventoryAdjusted` carries no tenant id, so manual adjustments are
    # still caught by the daily cron.
    dispatcher.register(VehicleLoaded, _check)


async def _collect_breaches(database: Database, tenant_id: uuid.UUID) -> list[dict[str, Any]]:
    from lpg.application.common.tenant import RequestTenantContext
    from lpg.infrastructure.jobs.inventory_jobs import check_reorder_levels_for_tenant
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    collected: list[dict[str, Any]] = []
    async for session in database.open_session(tenant_id=tenant_id):
        async with SqlAlchemyUnitOfWork(session, RequestTenantContext(tenant_id=tenant_id)) as uow:
            await check_reorder_levels_for_tenant(
                uow,
                None,
                tenant_id=tenant_id,
                record_predictions=False,
                collected=collected,
            )
            await uow.commit()
    return collected
