"""`send_notification` — the arq job for notification delivery.

Two kinds of caller enqueue it:

- **Domain-event handlers** (`events/notification_handlers.py` through
  `InAppFirstNotifier`) have already written the in-app rows in the API
  process and set ``in_app_delivered`` — the job only sends email / SMS /
  push.
- **Crons** (stale orders, auto-assignment fallbacks, compliance expiry,
  refill nudges, rate proposals, reorder points) enqueue a bare payload —
  the job writes the in-app rows too.

What each type says, who receives it and which channels it uses lives in
`infrastructure/notification/catalog.py`; recipient lookup in
`recipients.py`. The payload carries the type, ``tenant_id`` and the ids
the message is about (``order_id``, ``route_id``, ``complaint_id``, ...).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog

from lpg.infrastructure.notification.delivery import (
    IN_APP_DELIVERED,
    deliver_external,
    write_in_app,
)
from lpg.infrastructure.notification.recipients import NotificationResolver

if TYPE_CHECKING:
    from lpg.infrastructure.persistence.database import Database

_logger = structlog.get_logger(__name__)


async def send_notification(ctx: dict[str, Any], payload: dict[str, Any]) -> None:
    """Resolve recipients, write the in-app rows (unless the API process
    already did) and send the external channels, in one transaction with
    the delivery log."""
    structlog.contextvars.bind_contextvars(
        correlation_id=str(uuid.uuid4()),
        job_name="send_notification",
        tenant_id=payload.get("tenant_id"),
        notification_type=payload.get("type"),
    )
    from lpg.application.common.tenant import RequestTenantContext
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    tenant_id = uuid.UUID(str(payload["tenant_id"]))
    database: Database = ctx["database"]

    async for session in database.open_session(tenant_id=tenant_id):
        async with SqlAlchemyUnitOfWork(
            session,
            RequestTenantContext(tenant_id=tenant_id),
            event_dispatcher=ctx.get("event_dispatcher"),
        ) as uow:
            prepared = await NotificationResolver(uow, tenant_id).prepare(payload)
            if prepared is None:
                return
            if not payload.get(IN_APP_DELIVERED):
                await write_in_app(uow, prepared)
            await deliver_external(ctx, uow, database, prepared)
            await uow.commit()
            _logger.info(
                "notification_job_completed",
                recipients_count=len(prepared.recipient_user_ids),
            )
