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
    RouteStopsResequenced,
)
from lpg.domain.inventory.inventory_location import GoodsReceived, InventoryAdjusted
from lpg.domain.notification.in_app_notification import InAppNotificationCreated
from lpg.domain.order.order import OrderStatusChanged

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

    async def on_order_status_changed(event: OrderStatusChanged) -> None:
        """Every order transition, with its real from/to status.

        Subscribed to `OrderStatusChanged` rather than the transition-specific
        events: `dispatch`/`depart`/`reschedule` have no specific event, so
        `out_for_delivery` never reached a client before.
        """
        order_id = str(event.order_id)
        message = {
            "type": "order.status_changed",
            "order_id": order_id,
            "order_number": event.order_number,
            "from_status": event.from_status,
            "status": event.to_status,
            "changed_by": str(event.changed_by),
        }

        tenant = event.tenant_id
        # Per-order channel: whoever has that order's detail screen open.
        await publisher.publish(f"tenant:{tenant}:order:{order_id}", message)
        # Tenant-wide order feed: list screens (Order Queue) that need to
        # know *an* order changed without subscribing per row.
        await publisher.publish(f"tenant:{tenant}:orders", message)
        await publish_dashboard_update(event)

    async def on_notification_created(event: InAppNotificationCreated) -> None:
        """Notify user of new in-app notification.

        Carries the text and reference so a client can show it (toast,
        snackbar) and refresh the referenced screen without a fetch first.
        """
        channel = f"tenant:{getattr(event, 'tenant_id', 'global')}:user:{event.recipient_user_id}"
        message = {
            "type": "notification.new",
            "notification_id": str(event.notification_id),
            "notification_type": event.notification_type,
            "title": event.title,
            "body": event.body,
            "reference_type": event.reference_type,
            "reference_id": str(event.reference_id) if event.reference_id else None,
        }
        await publisher.publish(channel, message)

    async def on_route_status_changed(
        event: RoutePlanned
        | RouteStatusChanged
        | OrderAssignedToRoute
        | OrderDelivered
        | OrderDeliveryFailed
        | RouteStopsResequenced,
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
    dispatcher.register(OrderStatusChanged, on_order_status_changed)  # type: ignore[arg-type]

    # Notifications
    dispatcher.register(InAppNotificationCreated, on_notification_created)  # type: ignore[arg-type]

    # Route & Dispatch
    dispatcher.register(RoutePlanned, on_route_status_changed)  # type: ignore[arg-type]
    dispatcher.register(RouteStatusChanged, on_route_status_changed)  # type: ignore[arg-type]
    dispatcher.register(OrderAssignedToRoute, on_route_status_changed)  # type: ignore[arg-type]
    dispatcher.register(OrderDelivered, on_route_status_changed)  # type: ignore[arg-type]
    dispatcher.register(OrderDeliveryFailed, on_route_status_changed)  # type: ignore[arg-type]
    dispatcher.register(RouteStopsResequenced, on_route_status_changed)  # type: ignore[arg-type]

    # Drivers
    dispatcher.register(DriverRegistered, on_driver_updated)  # type: ignore[arg-type]
    dispatcher.register(DriverStatusChanged, on_driver_updated)  # type: ignore[arg-type]

    # Inventory updates affect dashboard
    dispatcher.register(GoodsReceived, publish_dashboard_update)
    dispatcher.register(InventoryAdjusted, publish_dashboard_update)
