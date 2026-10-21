"""Unit tests for the domain-event -> ARQ-job wiring in
`register_notification_handlers`.

The handlers are deliberately thin (no DB access — they only enqueue a
job); these check the right job is enqueued with the right payload.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from lpg.domain.accounting.cash_handover import CashShortfallDeclared
from lpg.domain.delivery.route import RouteLoadConfirmed, RouteStatusChanged
from lpg.domain.order.order import (
    BookingCancelled,
    BookingConfirmed,
    BookingCreated,
    CylinderDelivered,
    OrderStatusChanged,
)
from lpg.infrastructure.events.dispatcher import DomainEventDispatcher
from lpg.infrastructure.events.notification_handlers import (
    register_notification_handlers,
)


class _FakeJobQueue:
    def __init__(self) -> None:
        self.enqueued: list[tuple[str, dict[str, Any]]] = []

    async def enqueue(self, function_name: str, *args: Any, **_: Any) -> None:
        self.enqueued.append((function_name, args[0] if args else {}))

    async def notify(self, payload: dict[str, Any]) -> None:
        """The `Notifier` port — recorded like the job it used to enqueue."""
        self.enqueued.append(("send_notification", payload))


def _booking_created(source: str) -> BookingCreated:
    return BookingCreated(
        order_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        booking_source=source,
        requested_date=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_customer_placed_order_enqueues_a_staff_alert() -> None:
    queue = _FakeJobQueue()
    dispatcher = DomainEventDispatcher()
    register_notification_handlers(dispatcher, queue)

    event = _booking_created("mobile_app")
    await dispatcher.dispatch([event])

    assert (
        "send_notification",
        {
            "type": "order_placed_staff",
            "tenant_id": str(event.tenant_id),
            "order_id": str(event.order_id),
        },
    ) in queue.enqueued


@pytest.mark.asyncio
async def test_customer_placed_order_acknowledges_the_customer() -> None:
    queue = _FakeJobQueue()
    dispatcher = DomainEventDispatcher()
    register_notification_handlers(dispatcher, queue)

    event = _booking_created("mobile_app")
    await dispatcher.dispatch([event])

    assert (
        "send_notification",
        {
            "type": "order_placed",
            "tenant_id": str(event.tenant_id),
            "order_id": str(event.order_id),
        },
    ) in queue.enqueued


@pytest.mark.asyncio
async def test_staff_placed_order_notifies_no_one_on_creation() -> None:
    queue = _FakeJobQueue()
    dispatcher = DomainEventDispatcher()
    register_notification_handlers(dispatcher, queue)

    await dispatcher.dispatch([_booking_created("staff")])

    assert not any(
        payload.get("type") in {"order_placed_staff", "order_placed"}
        for _, payload in queue.enqueued
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["phone", "walk_in", "whatsapp", "api"])
async def test_every_non_staff_source_alerts_staff(source: str) -> None:
    queue = _FakeJobQueue()
    dispatcher = DomainEventDispatcher()
    register_notification_handlers(dispatcher, queue)

    await dispatcher.dispatch([_booking_created(source)])

    enqueued_types = {payload.get("type") for _, payload in queue.enqueued}
    assert "order_placed_staff" in enqueued_types
    assert "order_placed" in enqueued_types


@pytest.mark.asyncio
async def test_cash_shortfall_enqueues_a_staff_alert() -> None:
    queue = _FakeJobQueue()
    dispatcher = DomainEventDispatcher()
    register_notification_handlers(dispatcher, queue)

    event = CashShortfallDeclared(
        cash_handover_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        driver_id=uuid.uuid4(),
        route_id=uuid.uuid4(),
        expected_amount=Decimal("1811.00"),
        actual_amount=Decimal("1800.00"),
        shortfall=Decimal("11.00"),
    )
    await dispatcher.dispatch([event])

    assert (
        "send_notification",
        {
            "type": "cash_shortfall_staff",
            "tenant_id": str(event.tenant_id),
            "cash_handover_id": str(event.cash_handover_id),
            "route_id": str(event.route_id),
            "expected_amount": "1811.00",
            "actual_amount": "1800.00",
            "shortfall": "11.00",
        },
    ) in queue.enqueued


@pytest.mark.asyncio
async def test_route_load_confirmed_enqueues_a_staff_alert() -> None:
    queue = _FakeJobQueue()
    dispatcher = DomainEventDispatcher()
    register_notification_handlers(dispatcher, queue)

    event = RouteLoadConfirmed(
        route_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        driver_id=uuid.uuid4(),
        confirmed_by=uuid.uuid4(),
    )
    await dispatcher.dispatch([event])

    assert (
        "send_notification",
        {
            "type": "route_load_confirmed_staff",
            "tenant_id": str(event.tenant_id),
            "route_id": str(event.route_id),
            "driver_id": str(event.driver_id),
        },
    ) in queue.enqueued


@pytest.mark.asyncio
async def test_route_loaded_enqueues_a_route_ready_push_for_the_driver() -> None:
    queue = _FakeJobQueue()
    dispatcher = DomainEventDispatcher()
    register_notification_handlers(dispatcher, queue)

    event = RouteStatusChanged(
        route_id=uuid.uuid4(),
        old_status="planned",
        new_status="loaded",
        tenant_id=uuid.uuid4(),
        driver_id=uuid.uuid4(),
    )
    await dispatcher.dispatch([event])

    assert (
        "send_notification",
        {
            "type": "route_ready",
            "tenant_id": str(event.tenant_id),
            "driver_id": str(event.driver_id),
            "route_id": str(event.route_id),
        },
    ) in queue.enqueued


@pytest.mark.asyncio
@pytest.mark.parametrize("new_status", ["in_progress", "completed", "cancelled"])
async def test_route_status_other_than_loaded_enqueues_nothing(new_status: str) -> None:
    queue = _FakeJobQueue()
    dispatcher = DomainEventDispatcher()
    register_notification_handlers(dispatcher, queue)

    await dispatcher.dispatch(
        [
            RouteStatusChanged(
                route_id=uuid.uuid4(),
                old_status="loaded",
                new_status=new_status,
                tenant_id=uuid.uuid4(),
                driver_id=uuid.uuid4(),
            )
        ]
    )

    assert not any(p.get("type") == "route_ready" for _, p in queue.enqueued)


@pytest.mark.asyncio
async def test_booking_cancelled_enqueues_a_stop_cancelled_job() -> None:
    queue = _FakeJobQueue()
    dispatcher = DomainEventDispatcher()
    register_notification_handlers(dispatcher, queue)

    event = BookingCancelled(
        order_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        cancelled_by=uuid.uuid4(),
        approved_by=None,
        reason="customer changed their mind",
        cancellation_charge=None,
    )
    await dispatcher.dispatch([event])

    assert (
        "send_notification",
        {
            "type": "stop_cancelled",
            "tenant_id": str(event.tenant_id),
            "order_id": str(event.order_id),
        },
    ) in queue.enqueued


@pytest.mark.asyncio
async def test_booking_confirmed_still_notifies_the_customer() -> None:
    queue = _FakeJobQueue()
    dispatcher = DomainEventDispatcher()
    register_notification_handlers(dispatcher, queue)

    event = BookingConfirmed(
        order_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        confirmed_by=uuid.uuid4(),
        confirmed_at=datetime.now(UTC),
    )
    await dispatcher.dispatch([event])

    assert any(payload.get("type") == "booking_confirmed" for _, payload in queue.enqueued)


def _status_changed(to_status: str) -> OrderStatusChanged:
    return OrderStatusChanged(
        order_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        order_number="ORD000022",
        from_status="ready_for_dispatch",
        to_status=to_status,
        changed_by=uuid.uuid4(),
    )


@pytest.mark.asyncio
async def test_out_for_delivery_notifies_the_customer() -> None:
    queue = _FakeJobQueue()
    dispatcher = DomainEventDispatcher()
    register_notification_handlers(dispatcher, queue)

    event = _status_changed("out_for_delivery")
    await dispatcher.dispatch([event])

    assert queue.enqueued == [
        (
            "send_notification",
            {
                "type": "out_for_delivery",
                "tenant_id": str(event.tenant_id),
                "order_id": str(event.order_id),
            },
        )
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("to_status", ["confirmed", "assigned", "ready_for_dispatch", "delivered"])
async def test_other_status_changes_enqueue_no_out_for_delivery(to_status: str) -> None:
    queue = _FakeJobQueue()
    dispatcher = DomainEventDispatcher()
    register_notification_handlers(dispatcher, queue)

    await dispatcher.dispatch([_status_changed(to_status)])

    assert queue.enqueued == []


@pytest.mark.asyncio
async def test_route_started_alerts_staff() -> None:
    queue = _FakeJobQueue()
    dispatcher = DomainEventDispatcher()
    register_notification_handlers(dispatcher, queue)

    event = RouteStatusChanged(
        route_id=uuid.uuid4(),
        old_status="loaded",
        new_status="in_progress",
        tenant_id=uuid.uuid4(),
        driver_id=uuid.uuid4(),
    )
    await dispatcher.dispatch([event])

    assert queue.enqueued == [
        (
            "send_notification",
            {
                "type": "route_started_staff",
                "tenant_id": str(event.tenant_id),
                "route_id": str(event.route_id),
                "driver_id": str(event.driver_id),
            },
        )
    ]


@pytest.mark.asyncio
async def test_delivery_notifies_the_customer_and_staff() -> None:
    queue = _FakeJobQueue()
    dispatcher = DomainEventDispatcher()
    register_notification_handlers(dispatcher, queue)

    event = CylinderDelivered(
        order_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        route_stop_id=None,
        delivered_at=datetime.now(UTC),
    )
    await dispatcher.dispatch([event])

    types = [payload["type"] for _, payload in queue.enqueued]
    assert types == ["delivery_confirmed", "order_delivered_staff"]


# --- QA fixes (DO-27 / CA-05): every event the office, customer or driver
# --- must hear about produces a notification payload.


def _types(queue: _FakeJobQueue) -> list[str]:
    return [payload["type"] for _, payload in queue.enqueued]


async def _dispatch(event: Any) -> _FakeJobQueue:
    queue = _FakeJobQueue()
    dispatcher = DomainEventDispatcher()
    register_notification_handlers(dispatcher, queue)
    await dispatcher.dispatch([event])
    return queue


@pytest.mark.asyncio
async def test_cancellation_request_alerts_the_approvers_but_not_the_requester() -> None:
    from lpg.domain.order.order import CancellationRequested

    requester = uuid.uuid4()
    event = CancellationRequested(
        order_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        order_number="ORD000009",
        requested_by=requester,
        reason="Booked twice",
    )
    queue = await _dispatch(event)
    assert queue.enqueued == [
        (
            "send_notification",
            {
                "type": "cancellation_requested_staff",
                "tenant_id": str(event.tenant_id),
                "order_id": str(event.order_id),
                "reason": "Booked twice",
                "actor_id": str(requester),
            },
        )
    ]


@pytest.mark.asyncio
async def test_failed_delivery_tells_the_office_and_the_customer() -> None:
    from lpg.domain.order.order import DeliveryFailed

    event = DeliveryFailed(
        order_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        route_stop_id=uuid.uuid4(),
        reason_code="customer_unavailable",
        recorded_by=uuid.uuid4(),
    )
    queue = await _dispatch(event)
    assert _types(queue) == ["delivery_failed_staff", "delivery_failed_customer"]
    assert all(p["reason_code"] == "customer_unavailable" for _, p in queue.enqueued)


@pytest.mark.asyncio
async def test_cancellation_tells_the_customer_with_the_charge() -> None:
    event = BookingCancelled(
        order_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        cancelled_by=uuid.uuid4(),
        approved_by=uuid.uuid4(),
        reason="x",
        cancellation_charge=Decimal("50.00"),
    )
    queue = await _dispatch(event)
    assert _types(queue) == ["order_cancelled_customer", "stop_cancelled"]
    assert queue.enqueued[0][1]["cancellation_charge"] == "50.00"


@pytest.mark.asyncio
async def test_complaints_alert_staff_and_the_assignee() -> None:
    from lpg.domain.complaint.complaint import ComplaintAssigned, ComplaintRaised
    from lpg.domain.complaint.value_objects import ComplaintCategory, ComplaintPriority

    raised = ComplaintRaised(
        complaint_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        category=ComplaintCategory.SHORT_DELIVERY,
        priority=ComplaintPriority.HIGH,
        sla_due_at=datetime.now(UTC),
    )
    assert _types(await _dispatch(raised)) == ["complaint_raised_staff"]

    assignee, manager = uuid.uuid4(), uuid.uuid4()
    assigned = ComplaintAssigned(
        complaint_id=raised.complaint_id,
        tenant_id=raised.tenant_id,
        assigned_to=assignee,
        assigned_by=manager,
    )
    queue = await _dispatch(assigned)
    assert _types(queue) == ["complaint_assigned"]
    assert queue.enqueued[0][1]["assigned_to"] == str(assignee)

    self_assigned = ComplaintAssigned(
        complaint_id=raised.complaint_id,
        tenant_id=raised.tenant_id,
        assigned_to=manager,
        assigned_by=manager,
    )
    assert _types(await _dispatch(self_assigned)) == []


@pytest.mark.asyncio
async def test_online_payment_tells_customer_and_accounts_once() -> None:
    from lpg.domain.accounting.invoice import PaymentCollected
    from lpg.domain.accounting.online_payment import OnlinePaymentReceived

    online = OnlinePaymentReceived(
        online_payment_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        order_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        amount=Decimal("1811.00"),
        provider="razorpay",
        provider_payment_id="pay_1",
        paid_at=datetime.now(UTC),
    )
    queue = await _dispatch(online)
    assert _types(queue) == ["payment_received_customer", "payment_received_staff"]
    assert queue.enqueued[0][1]["amount"] == "1811.00"

    def _collected(method: str) -> PaymentCollected:
        return PaymentCollected(
            payment_id=uuid.uuid4(),
            tenant_id=online.tenant_id,
            invoice_id=uuid.uuid4(),
            method=method,
            amount=Decimal("1811.00"),
            collected_by=uuid.uuid4(),
            collected_at=datetime.now(UTC),
        )

    # The gateway payment applied to the invoice is not announced twice.
    assert _types(await _dispatch(_collected("online_gateway"))) == []
    assert _types(await _dispatch(_collected("cash"))) == ["payment_received_customer"]


@pytest.mark.asyncio
async def test_route_changes_reach_the_driver() -> None:
    from lpg.domain.delivery.route import RouteStopsResequenced

    tenant, route, driver = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    def _status(old: str, new: str) -> RouteStatusChanged:
        return RouteStatusChanged(
            route_id=route, old_status=old, new_status=new, tenant_id=tenant, driver_id=driver
        )

    assert _types(await _dispatch(_status("planned", "loaded"))) == ["route_ready"]
    assert _types(await _dispatch(_status("loaded", "cancelled"))) == ["route_cancelled_driver"]
    assert _types(await _dispatch(_status("planned", "cancelled"))) == []
    # A rescheduled stop reopening a finished trip is not "left the depot".
    assert _types(await _dispatch(_status("completed", "in_progress"))) == []
    resequenced = RouteStopsResequenced(
        route_id=route, tenant_id=tenant, old_order=(), new_order=()
    )
    assert _types(await _dispatch(resequenced)) == ["route_resequenced"]
