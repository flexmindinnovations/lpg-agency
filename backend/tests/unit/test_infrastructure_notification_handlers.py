"""Unit tests for the domain-event -> ARQ-job wiring in
`register_notification_handlers`.

The handlers are deliberately thin (no DB access — they only enqueue a
job); these check the right job is enqueued with the right payload.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

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
async def test_staff_placed_order_does_not_alert_staff() -> None:
    queue = _FakeJobQueue()
    dispatcher = DomainEventDispatcher()
    register_notification_handlers(dispatcher, queue)  # type: ignore[arg-type]

    await dispatcher.dispatch([_booking_created("staff")])

    assert not any(
        payload.get("type") == "order_placed_staff"
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

    assert any(
        payload.get("type") == "order_placed_staff"
        for _, payload in queue.enqueued
    )


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
