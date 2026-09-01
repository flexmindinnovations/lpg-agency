"""Unit tests for `publish_driver_location` — the transport-agnostic core of
the Driver App's live-location fan-out.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from lpg.application.common.errors import ConflictError, NotFoundError
from lpg.application.delivery.driver_location import (
    DriverLocationPing,
    publish_driver_location,
)
from lpg.domain.delivery.route import Route, RouteStop


class _FakeStore:
    def __init__(self) -> None:
        self.saved: list[tuple[uuid.UUID, uuid.UUID, dict[str, Any]]] = []

    async def save(
        self, tenant_id: uuid.UUID, route_id: uuid.UUID, snapshot: dict[str, Any]
    ) -> None:
        self.saved.append((tenant_id, route_id, snapshot))


class _FakePublisher:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, Any]]] = []

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        self.published.append((channel, message))


def _route(
    *, driver_id: uuid.UUID, tenant_id: uuid.UUID, status: str, order_ids: list[uuid.UUID]
) -> Route:
    route_id = uuid.uuid4()
    stops = [
        RouteStop(
            stop_id=uuid.uuid4(),
            route_id=route_id,
            order_id=order_id,
            sequence_number=i,
        )
        for i, order_id in enumerate(order_ids)
    ]
    return Route(
        route_id=route_id,
        tenant_id=tenant_id,
        branch_id=uuid.uuid4(),
        driver_id=driver_id,
        vehicle_id=uuid.uuid4(),
        status=status,
        stops=stops,
    )


_PING = DriverLocationPing(latitude=9.93, longitude=76.26, heading=90.0)


@pytest.mark.asyncio
async def test_caches_and_fans_out_to_every_order_on_the_route() -> None:
    driver_id, tenant_id = uuid.uuid4(), uuid.uuid4()
    order_a, order_b = uuid.uuid4(), uuid.uuid4()
    route = _route(
        driver_id=driver_id,
        tenant_id=tenant_id,
        status="in_progress",
        order_ids=[order_a, order_b],
    )
    store, publisher = _FakeStore(), _FakePublisher()

    snapshot = await publish_driver_location(
        route=route,
        acting_driver_id=driver_id,
        ping=_PING,
        store=store,
        publisher=publisher,
    )

    assert snapshot["latitude"] == 9.93
    assert len(store.saved) == 1
    assert store.saved[0][:2] == (tenant_id, route.id)

    channels = {channel for channel, _ in publisher.published}
    assert channels == {
        f"tenant:{tenant_id}:order:{order_a}",
        f"tenant:{tenant_id}:order:{order_b}",
    }
    for _, message in publisher.published:
        assert message["type"] == "driver.location"
        assert message["heading"] == 90.0
        assert "order_id" in message


@pytest.mark.asyncio
async def test_rejects_a_driver_who_does_not_own_the_route() -> None:
    route = _route(
        driver_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        status="in_progress",
        order_ids=[uuid.uuid4()],
    )
    store, publisher = _FakeStore(), _FakePublisher()

    with pytest.raises(NotFoundError):
        await publish_driver_location(
            route=route,
            acting_driver_id=uuid.uuid4(),  # someone else
            ping=_PING,
            store=store,
            publisher=publisher,
        )
    assert store.saved == []
    assert publisher.published == []


@pytest.mark.asyncio
async def test_rejects_a_route_that_is_not_in_progress() -> None:
    driver_id = uuid.uuid4()
    route = _route(
        driver_id=driver_id,
        tenant_id=uuid.uuid4(),
        status="loaded",
        order_ids=[uuid.uuid4()],
    )
    store, publisher = _FakeStore(), _FakePublisher()

    with pytest.raises(ConflictError):
        await publish_driver_location(
            route=route,
            acting_driver_id=driver_id,
            ping=_PING,
            store=store,
            publisher=publisher,
        )
    assert store.saved == []
    assert publisher.published == []


@pytest.mark.asyncio
async def test_rejects_a_missing_acting_driver() -> None:
    route = _route(
        driver_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        status="in_progress",
        order_ids=[uuid.uuid4()],
    )
    with pytest.raises(NotFoundError):
        await publish_driver_location(
            route=route,
            acting_driver_id=None,
            ping=_PING,
            store=_FakeStore(),
            publisher=_FakePublisher(),
        )
