"""Unit tests for the nearest-neighbour + 2-opt solver and
`OptimizeRouteSequenceUseCase` (AI Operational Intelligence, Horizon 1
Stage 5). Fake repositories, no DB.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from lpg.application.common.errors import RouteOptimizationDisabledError
from lpg.application.delivery.route_optimization import (
    OptimizeRouteSequenceCommand,
    OptimizeRouteSequenceUseCase,
    nearest_neighbour,
    two_opt,
)
from lpg.domain.delivery.route import Route
from lpg.domain.order.order import DeliveryAddress, Order, OrderLine
from lpg.domain.tenant.tenant_configuration import TenantConfiguration

if TYPE_CHECKING:
    from collections.abc import Sequence

    from lpg.application.ai.prediction import Prediction
    from lpg.application.delivery.ports import RouteStopOwner
    from lpg.application.order.ports import OrderStatusHistoryEntry
    from lpg.domain.common.base import DomainEvent


# --- nearest_neighbour / two_opt --------------------------------------------


def test_nearest_neighbour_visits_the_closest_unvisited_point_each_step() -> None:
    # A line: 0 -> 10 -> 11 -> 20 (degrees, roughly). Starting at index 0,
    # greedy should walk it left-to-right, not jump to the far end.
    coords = [(0.0, 0.0), (0.0, 20.0), (0.0, 10.0), (0.0, 11.0)]
    tour = nearest_neighbour(coords)
    assert tour[0] == 0
    assert tour == [0, 2, 3, 1]


def test_nearest_neighbour_handles_zero_and_one_points() -> None:
    assert nearest_neighbour([]) == []
    assert nearest_neighbour([(1.0, 1.0)]) == [0]


def test_two_opt_untangles_a_crossed_tour() -> None:
    # A square; a naive order that crosses itself (0 -> 2 -> 1 -> 3) is
    # longer than the perimeter walk (0 -> 1 -> 2 -> 3 or its reverse).
    coords = [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0)]
    crossed = [0, 2, 1, 3]
    improved = two_opt(crossed, coords)

    from lpg.application.delivery.route_optimization import _tour_length

    assert _tour_length(improved, coords) <= _tour_length(crossed, coords)
    assert _tour_length(improved, coords) == pytest.approx(_tour_length([0, 1, 2, 3], coords))


# --- OptimizeRouteSequenceUseCase --------------------------------------------


class _FakeUnitOfWork:
    def __init__(self) -> None:
        self.commits = 0

    async def __aenter__(self) -> _FakeUnitOfWork:
        return self

    async def __aexit__(self, *_: object) -> None:
        pass

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        pass

    def collect_events(self) -> Sequence[DomainEvent]:
        return []


class _FakeRouteRepository:
    def __init__(self, route: Route) -> None:
        self._route = route
        self.saved: list[Route] = []

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    async def save(self, route: Route) -> None:
        self.saved.append(route)

    async def get_by_id(self, route_id: uuid.UUID) -> Route | None:
        return self._route if self._route.id == route_id else None

    async def get_active_route_for_driver(self, driver_id: uuid.UUID) -> Route | None:
        raise NotImplementedError

    async def get_active_route_for_vehicle(self, vehicle_id: uuid.UUID) -> Route | None:
        raise NotImplementedError

    async def get_route_with_open_stop_for(
        self, driver_id: uuid.UUID, vehicle_id: uuid.UUID, route_date: object
    ) -> Route | None:
        raise NotImplementedError

    async def count_active_routes_for_order(self, order_id: uuid.UUID) -> int:
        raise NotImplementedError

    async def get_stop_owner(self, route_stop_id: uuid.UUID) -> RouteStopOwner | None:
        raise NotImplementedError

    async def list_routes(self, *args: object, **kwargs: object) -> list[Route]:
        raise NotImplementedError

    async def count_routes(self, *args: object, **kwargs: object) -> int:
        raise NotImplementedError


class _FakeOrderRepository:
    def __init__(self, orders: dict[uuid.UUID, Order]) -> None:
        self._orders = orders

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    async def save(self, order: Order) -> None:
        raise NotImplementedError

    async def get_by_id(self, order_id: uuid.UUID) -> Order | None:
        return self._orders.get(order_id)

    async def list_orders(self, *args: object, **kwargs: object) -> list[Order]:
        raise NotImplementedError

    async def count_orders(self, *args: object, **kwargs: object) -> int:
        raise NotImplementedError

    async def list_status_history(self, order_id: uuid.UUID) -> list[OrderStatusHistoryEntry]:
        raise NotImplementedError

    async def list_stale_unassigned(self, stale_after: object) -> list[Order]:
        raise NotImplementedError

    async def mark_stale_notified(self, order_id: uuid.UUID) -> None:
        raise NotImplementedError


class _FakePredictionRepository:
    def __init__(self) -> None:
        self.added: list[Prediction] = []

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    async def add(self, prediction: Prediction) -> None:
        self.added.append(prediction)

    async def latest_for_subject(
        self,
        *,
        prediction_type: str,  # noqa: ARG002 - Protocol keyword-only param
        subject_id: uuid.UUID,  # noqa: ARG002 - Protocol keyword-only param
    ) -> Prediction | None:
        return None

    async def list_latest_by_type(
        self,
        *,
        prediction_type: str,  # noqa: ARG002 - Protocol keyword-only param
    ) -> list[Prediction]:
        return []


class _FakeTenantConfigurationRepository:
    def __init__(self, *, route_optimization_enabled: bool) -> None:
        self._enabled = route_optimization_enabled

    async def list_for_tenant_and_key(
        self, tenant_id: uuid.UUID, config_key: str
    ) -> list[TenantConfiguration]:
        if config_key != "route_optimization_enabled":
            return []
        return [
            TenantConfiguration(
                uuid.uuid4(),
                tenant_id,
                "route_optimization_enabled",
                "true" if self._enabled else "false",
                datetime.now(UTC) - timedelta(days=1),
            )
        ]

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> list[TenantConfiguration]:
        raise NotImplementedError

    async def add(self, config: TenantConfiguration) -> None:
        raise NotImplementedError


def _order(*, lat: float | None, lon: float | None) -> Order:
    return Order(
        order_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        address_id=uuid.uuid4(),
        delivery_address=DeliveryAddress(address_line="1 Test Rd", latitude=lat, longitude=lon),
        booking_source="staff",
        requested_date=datetime.now(UTC),
        lines=[OrderLine(uuid.uuid4(), uuid.uuid4(), quantity_ordered=1)],
    )


def _route_with_orders(orders: list[Order]) -> Route:
    route = Route(
        route_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        driver_id=uuid.uuid4(),
        vehicle_id=uuid.uuid4(),
        status="planned",
    )
    for order in orders:
        route.assign_order(order.id)
    return route


@pytest.mark.asyncio
async def test_raises_when_the_tenant_has_not_opted_in() -> None:
    orders = [_order(lat=1.0, lon=1.0), _order(lat=2.0, lon=2.0)]
    route = _route_with_orders(orders)
    use_case = OptimizeRouteSequenceUseCase(
        _FakeRouteRepository(route),
        _FakeOrderRepository({o.id: o for o in orders}),
        _FakePredictionRepository(),
        _FakeTenantConfigurationRepository(route_optimization_enabled=False),
        _FakeUnitOfWork(),
    )
    with pytest.raises(RouteOptimizationDisabledError):
        await use_case.execute(
            OptimizeRouteSequenceCommand(tenant_id=route.tenant_id, route_id=route.id)
        )


@pytest.mark.asyncio
async def test_reorders_located_stops_and_records_a_prediction() -> None:
    # Three stops roughly on a line at lon 0, 10, 5 -- nearest-neighbour +
    # 2-opt should settle on visiting them in geographic order.
    far = _order(lat=0.0, lon=10.0)
    near = _order(lat=0.0, lon=0.0)
    middle = _order(lat=0.0, lon=5.0)
    orders = [far, near, middle]  # assigned in a deliberately poor order
    route = _route_with_orders(orders)
    prediction_repo = _FakePredictionRepository()
    route_repo = _FakeRouteRepository(route)

    use_case = OptimizeRouteSequenceUseCase(
        route_repo,
        _FakeOrderRepository({o.id: o for o in orders}),
        prediction_repo,
        _FakeTenantConfigurationRepository(route_optimization_enabled=True),
        _FakeUnitOfWork(),
    )
    result = await use_case.execute(
        OptimizeRouteSequenceCommand(tenant_id=route.tenant_id, route_id=route.id)
    )

    # Nearest-neighbour always starts from the route's own current first
    # stop (here `far`, since it was assigned first) -- on this 1D line
    # that's already an optimal path (far -> middle -> near has the same
    # total length as the reverse), so the *direction* isn't fixed, but
    # `middle` must land between the other two either way.
    stops_by_order = {s.order_id: s for s in route.stops}
    assert stops_by_order[middle.id].sequence_number == 2
    assert {stops_by_order[near.id].sequence_number, stops_by_order[far.id].sequence_number} == {
        1,
        3,
    }
    assert result.km_after <= result.km_before
    assert len(route_repo.saved) == 1
    assert len(prediction_repo.added) == 1
    assert prediction_repo.added[0].prediction_type == "route_sequence"
    assert prediction_repo.added[0].model_version == "route_nn_2opt_v1"


@pytest.mark.asyncio
async def test_unlocated_stops_are_appended_after_the_optimised_block() -> None:
    located_a = _order(lat=0.0, lon=0.0)
    located_b = _order(lat=0.0, lon=1.0)
    unlocated = _order(lat=None, lon=None)
    orders = [unlocated, located_b, located_a]
    route = _route_with_orders(orders)

    use_case = OptimizeRouteSequenceUseCase(
        _FakeRouteRepository(route),
        _FakeOrderRepository({o.id: o for o in orders}),
        _FakePredictionRepository(),
        _FakeTenantConfigurationRepository(route_optimization_enabled=True),
        _FakeUnitOfWork(),
    )
    result = await use_case.execute(
        OptimizeRouteSequenceCommand(tenant_id=route.tenant_id, route_id=route.id)
    )

    stops_by_order = {s.order_id: s for s in route.stops}
    assert stops_by_order[unlocated.id].sequence_number == 3
    assert result.ordered_stop_ids[-1] == stops_by_order[unlocated.id].id


@pytest.mark.asyncio
async def test_fewer_than_two_located_stops_is_a_harmless_no_op() -> None:
    only_located = _order(lat=0.0, lon=0.0)
    unlocated = _order(lat=None, lon=None)
    orders = [only_located, unlocated]
    route = _route_with_orders(orders)

    use_case = OptimizeRouteSequenceUseCase(
        _FakeRouteRepository(route),
        _FakeOrderRepository({o.id: o for o in orders}),
        _FakePredictionRepository(),
        _FakeTenantConfigurationRepository(route_optimization_enabled=True),
        _FakeUnitOfWork(),
    )
    result = await use_case.execute(
        OptimizeRouteSequenceCommand(tenant_id=route.tenant_id, route_id=route.id)
    )

    assert result.km_before == 0.0
    assert result.km_after == 0.0
    assert set(result.ordered_stop_ids) == {s.id for s in route.stops}
