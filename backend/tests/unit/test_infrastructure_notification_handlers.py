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
from lpg.domain.delivery.route import RouteStatusChanged
from lpg.domain.order.order import BookingConfirmed, BookingCreated
from lpg.infrastructure.events.dispatcher import DomainEventDispatcher
from lpg.infrastructure.events.notification_handlers import (
    register_notification_handlers,
)


class _FakeJobQueue:
    def __init__(self) -> None:
        self.enqueued: list[tuple[str, dict[str, Any]]] = []

    async def enqueue(self, function_name: str, *args: Any, **_: Any) -> None:
        self.enqueued.append((function_name, args[0] if args else {}))


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
    register_notification_handlers(dispatcher, queue)  # type: ignore[arg-type]

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
    register_notification_handlers(dispatcher, queue)  # type: ignore[arg-type]

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
    register_notification_handlers(dispatcher, queue)  # type: ignore[arg-type]

    await dispatcher.dispatch([_booking_created("staff")])

    assert not any(
        payload.get("type") in {"order_placed_staff", "order_placed"}
        for _, payload in queue.enqueued
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source", ["phone", "walk_in", "whatsapp", "api"]
)
async def test_every_non_staff_source_alerts_staff(source: str) -> None:
    queue = _FakeJobQueue()
    dispatcher = DomainEventDispatcher()
    register_notification_handlers(dispatcher, queue)  # type: ignore[arg-type]

    await dispatcher.dispatch([_booking_created(source)])

    enqueued_types = {payload.get("type") for _, payload in queue.enqueued}
    assert "order_placed_staff" in enqueued_types
    assert "order_placed" in enqueued_types


@pytest.mark.asyncio
async def test_cash_shortfall_enqueues_a_staff_alert() -> None:
    queue = _FakeJobQueue()
    dispatcher = DomainEventDispatcher()
    register_notification_handlers(dispatcher, queue)  # type: ignore[arg-type]

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
async def test_route_loaded_enqueues_a_route_ready_push_for_the_driver() -> None:
    queue = _FakeJobQueue()
    dispatcher = DomainEventDispatcher()
    register_notification_handlers(dispatcher, queue)  # type: ignore[arg-type]

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
    register_notification_handlers(dispatcher, queue)  # type: ignore[arg-type]

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
async def test_booking_confirmed_still_notifies_the_customer() -> None:
    queue = _FakeJobQueue()
    dispatcher = DomainEventDispatcher()
    register_notification_handlers(dispatcher, queue)  # type: ignore[arg-type]

    event = BookingConfirmed(
        order_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        confirmed_by=uuid.uuid4(),
        confirmed_at=datetime.now(UTC),
    )
    await dispatcher.dispatch([event])

    assert any(
        payload.get("type") == "booking_confirmed"
        for _, payload in queue.enqueued
    )
