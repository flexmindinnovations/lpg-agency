"""Notification domain event handlers."""

import structlog

from lpg.domain.accounting.cash_handover import CashShortfallDeclared
from lpg.domain.accounting.invoice import InvoiceGenerated
from lpg.domain.common.base import DomainEvent
from lpg.domain.delivery.route import OrderAssignedToRoute, RouteStatusChanged
from lpg.domain.order.order import (
    BookingCancelled,
    BookingConfirmed,
    BookingCreated,
    CylinderDelivered,
    DeliveryFailed,
)
from lpg.infrastructure.events.dispatcher import DomainEventDispatcher
from lpg.infrastructure.jobs.pool import JobQueue

_logger = structlog.get_logger(__name__)


def register_notification_handlers(
    dispatcher: DomainEventDispatcher,
    job_queue: JobQueue,
) -> None:
    """Register notification handlers.

    Handlers are intentionally thin — no DB access here. They only enqueue an ARQ job.
    """

    async def _on_booking_created(event: DomainEvent) -> None:
        assert isinstance(event, BookingCreated)
        # Skip orders the staff created themselves in the dashboard — they
        # already know. Everything else (mobile_app, phone, walk_in,
        # whatsapp, api) is an order that arrived and needs someone to
        # confirm it.
        if event.booking_source == "staff":
            return
        # In-app only (see `_should_send_*` in `notification_jobs.py`) —
        # staff live in the dashboard, not the mobile apps that register
        # push tokens.
        await job_queue.enqueue(
            "send_notification",
            {
                "type": "order_placed_staff",
                "tenant_id": str(event.tenant_id),
                "order_id": str(event.order_id),
            },
        )
        # Acknowledge the customer immediately — `booking_confirmed` only
        # fires once the agency confirms, which can be minutes to hours
        # later. This closes the loop at the moment the order is placed.
        await job_queue.enqueue(
            "send_notification",
            {
                "type": "order_placed",
                "tenant_id": str(event.tenant_id),
                "order_id": str(event.order_id),
            },
        )

    async def _on_booking_confirmed(event: DomainEvent) -> None:
        assert isinstance(event, BookingConfirmed)
        await job_queue.enqueue(
            "send_notification",
            {
                "type": "booking_confirmed",
                "tenant_id": str(event.tenant_id),
                "order_id": str(event.order_id),
            },
        )

    async def _on_order_assigned(event: DomainEvent) -> None:
        assert isinstance(event, OrderAssignedToRoute)
        await job_queue.enqueue(
            "send_notification",
            {
                "type": "driver_assigned",
                "tenant_id": str(event.tenant_id),
                "order_id": str(event.order_id),
            },
        )

    async def _on_route_status_changed(event: DomainEvent) -> None:
        assert isinstance(event, RouteStatusChanged)
        # `planned -> loaded` = the vehicle's packed and the driver should
        # head out. One push per route (the job resolves the stop count),
        # replacing the per-order `driver_assigned` push while the route was
        # still being built.
        if event.new_status != "loaded":
            return
        await job_queue.enqueue(
            "send_notification",
            {
                "type": "route_ready",
                "tenant_id": str(event.tenant_id),
                "driver_id": str(event.driver_id),
                "route_id": str(event.route_id),
            },
        )

        # TODO: a customer-facing "out for delivery" per order on
        # `-> in_progress` still isn't wired (the `out_for_delivery` type's
        # title/body/push flags exist but nothing enqueues it).

    async def _on_cylinder_delivered(event: DomainEvent) -> None:
        assert isinstance(event, CylinderDelivered)
        await job_queue.enqueue(
            "send_notification",
            {
                "type": "delivery_confirmed",
                "tenant_id": str(event.tenant_id),
                "order_id": str(event.order_id),
            },
        )

    async def _on_invoice_generated(event: DomainEvent) -> None:
        assert isinstance(event, InvoiceGenerated)
        await job_queue.enqueue(
            "send_notification",
            {
                "type": "invoice_generated",
                "tenant_id": str(event.tenant_id),
                "order_id": str(event.order_id),
            },
        )

    async def _on_cash_shortfall_declared(event: DomainEvent) -> None:
        assert isinstance(event, CashShortfallDeclared)
        # The office needs to know a driver handed over less cash than the
        # route's deliveries collected (BR-32). Fires only on a genuine
        # shortfall — `CashHandover.declare` records no event when the
        # amounts match or the driver hands over more.
        await job_queue.enqueue(
            "send_notification",
            {
                "type": "cash_shortfall_staff",
                "tenant_id": str(event.tenant_id),
                "cash_handover_id": str(event.cash_handover_id),
                "route_id": str(event.route_id),
                "expected_amount": str(event.expected_amount),
                "actual_amount": str(event.actual_amount),
                "shortfall": str(event.shortfall),
            },
        )

    async def _on_booking_cancelled(event: DomainEvent) -> None:
        assert isinstance(event, BookingCancelled)
        # Only matters to a driver who's already out running the route the
        # cancelled order was on — the job resolves the stop -> route ->
        # driver and drops it unless the route is `in_progress`.
        await job_queue.enqueue(
            "send_notification",
            {
                "type": "stop_cancelled",
                "tenant_id": str(event.tenant_id),
                "order_id": str(event.order_id),
            },
        )

    async def _on_delivery_failed(event: DomainEvent) -> None:
        assert isinstance(event, DeliveryFailed)
        # We need branch_id for staff resolution, which isn't on DeliveryFailed.
        # send_notification job will have to fetch the order to get the branch_id.
        # We'll pass order_id and the job will fetch it.
        await job_queue.enqueue(
            "send_notification",
            {
                "type": "delivery_failed_staff",
                "tenant_id": str(event.tenant_id),
                "order_id": str(event.order_id),
            },
        )

    dispatcher.register(BookingCreated, _on_booking_created)
    dispatcher.register(BookingConfirmed, _on_booking_confirmed)
    dispatcher.register(OrderAssignedToRoute, _on_order_assigned)
    dispatcher.register(RouteStatusChanged, _on_route_status_changed)
    dispatcher.register(CylinderDelivered, _on_cylinder_delivered)
    dispatcher.register(InvoiceGenerated, _on_invoice_generated)
    dispatcher.register(DeliveryFailed, _on_delivery_failed)
    dispatcher.register(CashShortfallDeclared, _on_cash_shortfall_declared)
    dispatcher.register(BookingCancelled, _on_booking_cancelled)
