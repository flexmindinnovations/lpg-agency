"""Auto-assignment domain event handlers.

Kept separate from `notification_handlers.py` — same trigger event
(`BookingConfirmed`), different concern. Handlers stay "thin, no DB
access" (the same rule `notification_handlers.py` documents): this one
only enqueues an ARQ job; the actual kill-switch check, driver/vehicle
selection, and assignment mutation all happen inside
`infrastructure/jobs/auto_assignment_jobs.py`, where a database session
already exists.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from lpg.domain.order.order import BookingConfirmed

if TYPE_CHECKING:
    from lpg.domain.common.base import DomainEvent
    from lpg.infrastructure.events.dispatcher import DomainEventDispatcher
    from lpg.infrastructure.jobs.pool import JobQueue

_logger = structlog.get_logger(__name__)


def register_auto_assignment_handlers(
    dispatcher: DomainEventDispatcher,
    job_queue: JobQueue,
) -> None:
    """Registers the `BookingConfirmed` -> `auto_assign_driver` trigger."""

    async def _on_booking_confirmed(event: DomainEvent) -> None:
        assert isinstance(event, BookingConfirmed)
        await job_queue.enqueue(
            "auto_assign_driver",
            tenant_id=str(event.tenant_id),
            order_id=str(event.order_id),
            # Deterministic id — ARQ's own dedupe primitive (same pattern
            # `check_compliance_expiry` uses) — a retried or overlapping
            # dispatch of the same event enqueues this job at most once per
            # order. The job itself adds a second idempotency layer on top
            # (re-checking the order is still `confirmed` before acting),
            # since a human could still race ahead of even a deduped job.
            _job_id=f"auto_assign_{event.order_id}",
        )

    dispatcher.register(BookingConfirmed, _on_booking_confirmed)
