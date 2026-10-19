"""Unit tests for the domain-event -> Redis Pub/Sub wiring in
`register_realtime_handlers` and the per-process `ConnectionManager`."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest

from lpg.domain.notification.in_app_notification import InAppNotification
from lpg.domain.order.order import OrderStatusChanged
from lpg.infrastructure.events.dispatcher import DomainEventDispatcher
from lpg.infrastructure.events.realtime_handlers import register_realtime_handlers
from lpg.infrastructure.realtime.connection_manager import ConnectionManager


class _FakePublisher:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, Any]]] = []

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        self.published.append((channel, message))


class _FakeSocket:
    def __init__(self) -> None:
        self.sent: list[Any] = []

    async def send_json(self, data: Any) -> None:
        self.sent.append(data)


@pytest.mark.asyncio
async def test_status_change_reaches_the_order_and_tenant_feeds_with_the_real_status() -> None:
    publisher = _FakePublisher()
    dispatcher = DomainEventDispatcher()
    register_realtime_handlers(dispatcher, publisher)

    event = OrderStatusChanged(
        order_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        order_number="ORD000022",
        from_status="ready_for_dispatch",
        to_status="out_for_delivery",
        changed_by=uuid.uuid4(),
    )
    await dispatcher.dispatch([event])

    channels = [channel for channel, _ in publisher.published]
    tenant = event.tenant_id
    assert channels == [
        f"tenant:{tenant}:order:{event.order_id}",
        f"tenant:{tenant}:orders",
        f"tenant:{tenant}:dashboard",
    ]
    message = publisher.published[0][1]
    assert message == {
        "type": "order.status_changed",
        "order_id": str(event.order_id),
        "order_number": "ORD000022",
        "from_status": "ready_for_dispatch",
        "status": "out_for_delivery",
        "changed_by": str(event.changed_by),
    }


@pytest.mark.asyncio
async def test_new_notification_carries_its_text_and_reference() -> None:
    publisher = _FakePublisher()
    dispatcher = DomainEventDispatcher()
    register_realtime_handlers(dispatcher, publisher)

    order_id = uuid.uuid4()
    notification = InAppNotification.create(
        tenant_id=uuid.uuid4(),
        recipient_user_id=uuid.uuid4(),
        notification_type="out_for_delivery",
        title="Out for Delivery",
        body="Your order #ORD000022 is out for delivery.",
        reference_type="order",
        reference_id=order_id,
    )
    await dispatcher.dispatch(notification.events)

    channel, message = publisher.published[0]
    assert channel.endswith(f":user:{notification.recipient_user_id}")
    assert message["title"] == "Out for Delivery"
    assert message["body"] == "Your order #ORD000022 is out for delivery."
    assert message["reference_type"] == "order"
    assert message["reference_id"] == str(order_id)


@pytest.mark.asyncio
async def test_a_second_subscribe_adds_channels_without_dropping_the_first() -> None:
    manager = ConnectionManager()
    socket = _FakeSocket()

    await manager.connect(socket, ["tenant:t:notifications"])
    await manager.connect(socket, ["tenant:t:orders"])

    await manager.broadcast("tenant:t:notifications", {"n": 1})
    await manager.broadcast("tenant:t:orders", {"n": 2})
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert socket.sent == [{"n": 1}, {"n": 2}]
    assert manager.active_connection_count == 1

    await manager.disconnect(socket)
    assert manager.get_subscribed_channels() == []
