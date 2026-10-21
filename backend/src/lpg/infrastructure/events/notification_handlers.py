"""Notification domain event handlers.

Each handler maps one domain event to notification payloads — the type and
the ids the message is about — and hands them to a `Notifier`. In the API
process that is `InAppFirstNotifier`: the in-app rows (bell, customer
inbox, driver Alerts) are written right after the triggering transaction
commits and published live over `/ws`; email / SMS / push go to the arq
worker. Who receives what, and the wording, live in
`infrastructure/notification/catalog.py`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lpg.domain.accounting.cash_handover import CashShortfallDeclared
from lpg.domain.accounting.invoice import InvoiceGenerated, InvoiceSentToCustomer, PaymentCollected
from lpg.domain.accounting.online_payment import OnlinePaymentReceived
from lpg.domain.complaint.complaint import ComplaintAssigned, ComplaintRaised
from lpg.domain.delivery.route import (
    OrderAssignedToRoute,
    RouteLoadConfirmed,
    RouteStatusChanged,
    RouteStopsResequenced,
)
from lpg.domain.order.order import (
    BookingCancelled,
    BookingConfirmed,
    BookingCreated,
    CancellationRequested,
    CylinderDelivered,
    DeliveryFailed,
    OrderStatusChanged,
)

if TYPE_CHECKING:
    from lpg.domain.common.base import DomainEvent
    from lpg.infrastructure.events.dispatcher import DomainEventDispatcher
    from lpg.infrastructure.notification.delivery import Notifier

#: Gateway payments are announced once, by `OnlinePaymentReceived`, not
#: again when they are applied to the invoice.
_ONLINE_GATEWAY_METHOD = "online_gateway"


def register_notification_handlers(dispatcher: DomainEventDispatcher, notifier: Notifier) -> None:
    """Register notification handlers. Thin: no DB access here."""

    async def notify(notification_type: str, event: Any, **ids: object) -> None:
        payload: dict[str, Any] = {
            "type": notification_type,
            "tenant_id": str(event.tenant_id),
        }
        payload.update({k: str(v) for k, v in ids.items() if v is not None})
        await notifier.notify(payload)

    async def _on_booking_created(event: DomainEvent) -> None:
        assert isinstance(event, BookingCreated)
        # Orders the staff created themselves in the dashboard need no alert
        # — they already know. Everything else (app, phone, WhatsApp, ...)
        # is waiting for someone to confirm it.
        if event.booking_source == "staff":
            return
        await notify("order_placed_staff", event, order_id=event.order_id)
        # Acknowledge the customer at once — confirmation can be hours away.
        await notify("order_placed", event, order_id=event.order_id)

    async def _on_booking_confirmed(event: DomainEvent) -> None:
        assert isinstance(event, BookingConfirmed)
        await notify("booking_confirmed", event, order_id=event.order_id)

    async def _on_cancellation_requested(event: DomainEvent) -> None:
        assert isinstance(event, CancellationRequested)
        await notify(
            "cancellation_requested_staff",
            event,
            order_id=event.order_id,
            reason=event.reason,
            actor_id=event.requested_by,
        )

    async def _on_order_assigned(event: DomainEvent) -> None:
        assert isinstance(event, OrderAssignedToRoute)
        # Only reaches the driver once the trip is already theirs (loaded or
        # out) — while it is being built, `route_ready` covers every stop.
        await notify("driver_assigned", event, order_id=event.order_id, route_id=event.route_id)

    async def _on_route_status_changed(event: DomainEvent) -> None:
        assert isinstance(event, RouteStatusChanged)
        ids = {"route_id": event.route_id, "driver_id": event.driver_id}
        if event.new_status == "loaded":
            # The trip sheet is ready: the driver's "new trip" alert.
            await notify("route_ready", event, **ids)
        elif event.new_status == "in_progress" and event.old_status in ("planned", "loaded"):
            # The office sees the van leave — once per trip, not when a
            # rescheduled stop reopens a completed trip.
            await notify("route_started_staff", event, **ids)
        elif event.new_status == "cancelled" and event.old_status == "loaded":
            await notify("route_cancelled_driver", event, **ids)

    async def _on_route_resequenced(event: DomainEvent) -> None:
        assert isinstance(event, RouteStopsResequenced)
        await notify("route_resequenced", event, route_id=event.route_id)

    async def _on_order_status_changed(event: DomainEvent) -> None:
        assert isinstance(event, OrderStatusChanged)
        # `depart()` has no transition-specific event.
        if event.to_status == "out_for_delivery":
            await notify("out_for_delivery", event, order_id=event.order_id)

    async def _on_cylinder_delivered(event: DomainEvent) -> None:
        assert isinstance(event, CylinderDelivered)
        await notify("delivery_confirmed", event, order_id=event.order_id)
        await notify("order_delivered_staff", event, order_id=event.order_id)

    async def _on_delivery_failed(event: DomainEvent) -> None:
        assert isinstance(event, DeliveryFailed)
        await notify(
            "delivery_failed_staff",
            event,
            order_id=event.order_id,
            reason_code=event.reason_code,
            actor_id=event.recorded_by,
        )
        await notify(
            "delivery_failed_customer",
            event,
            order_id=event.order_id,
            reason_code=event.reason_code,
        )

    async def _on_booking_cancelled(event: DomainEvent) -> None:
        assert isinstance(event, BookingCancelled)
        charge = event.cancellation_charge
        await notify(
            "order_cancelled_customer",
            event,
            order_id=event.order_id,
            cancellation_charge=charge if charge else None,
        )
        # A driver who already has the trip (loaded / out) is told to skip
        # the stop; the resolver drops it otherwise.
        await notify("stop_cancelled", event, order_id=event.order_id)

    async def _on_invoice_generated(event: DomainEvent) -> None:
        assert isinstance(event, InvoiceGenerated)
        await notify(
            "invoice_generated", event, order_id=event.order_id, invoice_id=event.invoice_id
        )

    async def _on_invoice_sent(event: DomainEvent) -> None:
        assert isinstance(event, InvoiceSentToCustomer)
        await notify("invoice_sent", event, order_id=event.order_id, invoice_id=event.invoice_id)

    async def _on_online_payment_received(event: DomainEvent) -> None:
        assert isinstance(event, OnlinePaymentReceived)
        ids = {"order_id": event.order_id, "amount": event.amount}
        await notify("payment_received_customer", event, **ids)
        await notify("payment_received_staff", event, **ids)

    async def _on_payment_collected(event: DomainEvent) -> None:
        assert isinstance(event, PaymentCollected)
        if event.method == _ONLINE_GATEWAY_METHOD:
            return
        await notify(
            "payment_received_customer",
            event,
            invoice_id=event.invoice_id,
            amount=event.amount,
        )

    async def _on_complaint_raised(event: DomainEvent) -> None:
        assert isinstance(event, ComplaintRaised)
        await notify("complaint_raised_staff", event, complaint_id=event.complaint_id)

    async def _on_complaint_assigned(event: DomainEvent) -> None:
        assert isinstance(event, ComplaintAssigned)
        if event.assigned_to == event.assigned_by:
            return  # took it themselves
        await notify(
            "complaint_assigned",
            event,
            complaint_id=event.complaint_id,
            assigned_to=event.assigned_to,
        )

    async def _on_cash_shortfall_declared(event: DomainEvent) -> None:
        assert isinstance(event, CashShortfallDeclared)
        # Fires only on a genuine shortfall (BR-32).
        await notify(
            "cash_shortfall_staff",
            event,
            cash_handover_id=event.cash_handover_id,
            route_id=event.route_id,
            expected_amount=event.expected_amount,
            actual_amount=event.actual_amount,
            shortfall=event.shortfall,
        )

    async def _on_route_load_confirmed(event: DomainEvent) -> None:
        assert isinstance(event, RouteLoadConfirmed)
        await notify(
            "route_load_confirmed_staff",
            event,
            route_id=event.route_id,
            driver_id=event.driver_id,
        )

    dispatcher.register(BookingCreated, _on_booking_created)
    dispatcher.register(BookingConfirmed, _on_booking_confirmed)
    dispatcher.register(CancellationRequested, _on_cancellation_requested)
    dispatcher.register(OrderAssignedToRoute, _on_order_assigned)
    dispatcher.register(RouteStatusChanged, _on_route_status_changed)
    dispatcher.register(RouteStopsResequenced, _on_route_resequenced)
    dispatcher.register(OrderStatusChanged, _on_order_status_changed)
    dispatcher.register(CylinderDelivered, _on_cylinder_delivered)
    dispatcher.register(DeliveryFailed, _on_delivery_failed)
    dispatcher.register(BookingCancelled, _on_booking_cancelled)
    dispatcher.register(InvoiceGenerated, _on_invoice_generated)
    dispatcher.register(InvoiceSentToCustomer, _on_invoice_sent)
    dispatcher.register(OnlinePaymentReceived, _on_online_payment_received)
    dispatcher.register(PaymentCollected, _on_payment_collected)
    dispatcher.register(ComplaintRaised, _on_complaint_raised)
    dispatcher.register(ComplaintAssigned, _on_complaint_assigned)
    dispatcher.register(CashShortfallDeclared, _on_cash_shortfall_declared)
    dispatcher.register(RouteLoadConfirmed, _on_route_load_confirmed)
