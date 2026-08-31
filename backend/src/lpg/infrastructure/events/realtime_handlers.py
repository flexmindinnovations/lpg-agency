"""Real-time domain event handlers (``16-realtime-architecture.md`` §3.1).

Maps domain events to client-facing JSON messages and publishes them via
the ``RealtimePublisher``. These run synchronously after commit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lpg.domain.delivery.driver import DriverRegistered, DriverStatusChanged
from lpg.domain.delivery.route import (
    OrderAssignedToRoute,
    OrderDelivered,
    OrderDeliveryFailed,
    RoutePlanned,
    RouteStatusChanged,
)
from lpg.domain.inventory.inventory_location import GoodsReceived, InventoryAdjusted
from lpg.domain.notification.in_app_notification import InAppNotificationCreated
from lpg.domain.order.order import (
    BookingCancelled,
    BookingConfirmed,
    BookingCreated,
    CylinderDelivered,
    DeliveryFailed,
    InventoryReserved,
    OrderClosed,
)

if TYPE_CHECKING:
    from lpg.application.common.ports import RealtimePublisher
    from lpg.infrastructure.events.dispatcher import DomainEventDispatcher


def register_realtime_handlers(
    dispatcher: DomainEventDispatcher, publisher: RealtimePublisher
) -> None:
    """Register handlers to publish domain events to Redis Pub/Sub."""

    async def publish_dashboard_update(event: Any) -> None:
        """Dashboard live updates need to refresh when metrics change."""
        channel = f"tenant:{getattr(event, 'tenant_id', 'global')}:dashboard"
        message = {"type": "dashboard.metrics_stale"}
        await publisher.publish(channel, message)

    async def on_order_status_changed(
        event: BookingCreated
        | BookingConfirmed
        | BookingCancelled
        | InventoryReserved
        | CylinderDelivered
        | DeliveryFailed
        | OrderClosed,
    ) -> None:
        """Notify order state changes to the specific order channel and dashboard."""
        order_id = str(getattr(event, "order_id", getattr(event, "booking_id", "")))
        if not order_id:
            return

        status = (
            type(event)
            .__name__.replace("Booking", "")
            .replace("Order", "")
            .replace("Cylinder", "")
            .lower()
        )
        message = {
            "type": "order.status_changed",
            "order_id": order_id,
            "event": type(event).__name__,
            "status": status,
        }

        tenant = getattr(event, "tenant_id", "global")
        # Per-order channel: whoever has that order's detail screen open.
        await publisher.publish(f"tenant:{tenant}:order:{order_id}", message)
        # Tenant-wide order feed: list screens (Order Queue) that need to
        # know *an* order changed without subscribing per row.
        await publisher.publish(f"tenant:{tenant}:orders", message)
        await publish_dashboard_update(event)

    async def on_notification_created(event: InAppNotificationCreated) -> None:
        """Notify user of new in-app notification."""
        channel = f"tenant:{getattr(event, 'tenant_id', 'global')}:user:{event.recipient_user_id}"
        message = {
            "type": "notification.new",
            "notification_id": str(event.notification_id),
        }
        await publisher.publish(channel, message)

    async def on_route_status_changed(
        event: RoutePlanned
        | RouteStatusChanged
        | OrderAssignedToRoute
        | OrderDelivered
        | OrderDeliveryFailed,
    ) -> None:
        """Notify dispatch and drivers of route updates."""
        message = {
            "type": "delivery.route_updated",
            "route_id": str(event.route_id),
            "event": type(event).__name__,
        }
        await publisher.publish(f"tenant:{getattr(event, 'tenant_id', 'global')}:dispatch", message)

        if hasattr(event, "driver_id") and event.driver_id:
            await publisher.publish(
                f"tenant:{getattr(event, 'tenant_id', 'global')}:driver:{event.driver_id}", message
            )

        if isinstance(event, (OrderDelivered, OrderDeliveryFailed)):
            await publish_dashboard_update(event)

    async def on_driver_updated(event: DriverRegistered | DriverStatusChanged) -> None:
        message = {
            "type": "driver.updated",
            "driver_id": str(event.driver_id),
            "event": type(event).__name__,
        }
        await publisher.publish(f"tenant:{getattr(event, 'tenant_id', 'global')}:dispatch", message)

    # Order lifecycle
    dispatcher.register(BookingCreated, on_order_status_changed)  # type: ignore[arg-type]
    dispatcher.register(BookingConfirmed, on_order_status_changed)  # type: ignore[arg-type]
    dispatcher.register(BookingCancelled, on_order_status_changed)  # type: ignore[arg-type]
    dispatcher.register(InventoryReserved, on_order_status_changed)  # type: ignore[arg-type]
    dispatcher.register(CylinderDelivered, on_order_status_changed)  # type: ignore[arg-type]
    dispatcher.register(DeliveryFailed, on_order_status_changed)  # type: ignore[arg-type]
    dispatcher.register(OrderClosed, on_order_status_changed)  # type: ignore[arg-type]

    # Notifications
    dispatcher.register(InAppNotificationCreated, on_notification_created)  # type: ignore[arg-type]

    # Route & Dispatch
    dispatcher.register(RoutePlanned, on_route_status_changed)  # type: ignore[arg-type]
    dispatcher.register(RouteStatusChanged, on_route_status_changed)  # type: ignore[arg-type]
    dispatcher.register(OrderAssignedToRoute, on_route_status_changed)  # type: ignore[arg-type]
    dispatcher.register(OrderDelivered, on_route_status_changed)  # type: ignore[arg-type]
    dispatcher.register(OrderDeliveryFailed, on_route_status_changed)  # type: ignore[arg-type]

    # Drivers
    dispatcher.register(DriverRegistered, on_driver_updated)  # type: ignore[arg-type]
    dispatcher.register(DriverStatusChanged, on_driver_updated)  # type: ignore[arg-type]

    # Inventory updates affect dashboard
    dispatcher.register(GoodsReceived, publish_dashboard_update)
    dispatcher.register(InventoryAdjusted, publish_dashboard_update)
