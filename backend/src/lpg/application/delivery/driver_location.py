"""Live driver-location fan-out.

A GPS ping from the Driver App is *not* a domain fact — it is transient
telemetry with a short useful life. It is deliberately kept out of the
`Route` aggregate and the transactional path: the ping is written to a
short-TTL cache entry (last-known position) and published on each of the
route's per-order real-time channels, and that is all.

``publish_driver_location`` is the transport-agnostic core, exercised
directly by unit tests. The FastAPI handler in ``routers/route.py`` fetches
the ``Route`` and supplies the concrete cache/publisher.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol

from lpg.application.common.errors import ConflictError, NotFoundError

if TYPE_CHECKING:
    import uuid

    from lpg.application.common.ports import RealtimePublisher
    from lpg.domain.delivery.route import Route


@dataclass(frozen=True, slots=True)
class DriverLocationPing:
    latitude: float
    longitude: float
    heading: float | None = None
    speed_kph: float | None = None
    accuracy_m: float | None = None


class DriverLocationStore(Protocol):
    """Last-known driver position, keyed by route, with a short TTL."""

    async def save(
        self, tenant_id: uuid.UUID, route_id: uuid.UUID, snapshot: dict[str, Any]
    ) -> None: ...

    async def read(
        self, tenant_id: uuid.UUID, route_id: uuid.UUID
    ) -> dict[str, Any] | None: ...


def _snapshot(ping: DriverLocationPing, *, at: datetime) -> dict[str, Any]:
    return {
        "latitude": ping.latitude,
        "longitude": ping.longitude,
        "heading": ping.heading,
        "speed_kph": ping.speed_kph,
        "accuracy_m": ping.accuracy_m,
        "recorded_at": at.isoformat(),
    }


async def publish_driver_location(
    *,
    route: Route,
    acting_driver_id: uuid.UUID | None,
    ping: DriverLocationPing,
    store: DriverLocationStore,
    publisher: RealtimePublisher,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Authorize, cache the last-known position, and fan the ping out to every
    order on the route. Returns the stored snapshot.

    - ``NotFoundError`` if the caller isn't the route's own driver — a 404,
      not a 403, so a driver can't probe for other drivers' route ids.
    - ``ConflictError`` (409) if the route isn't ``in_progress``.
    """
    if acting_driver_id is None or route.driver_id != acting_driver_id:
        msg = f"No route visible with id {route.id}."
        raise NotFoundError(msg, route_id=str(route.id))

    if route.status != "in_progress":
        msg = "Location updates are only accepted while the route is in progress."
        raise ConflictError(msg)

    snapshot = _snapshot(ping, at=now or datetime.now(UTC))
    await store.save(route.tenant_id, route.id, snapshot)

    message = {"type": "driver.location", **snapshot}
    for stop in route.stops:
        await publisher.publish(
            f"tenant:{route.tenant_id}:order:{stop.order_id}",
            {**message, "order_id": str(stop.order_id)},
        )

    return snapshot
