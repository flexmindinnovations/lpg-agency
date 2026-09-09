"""Unit tests for `SuggestDriverAndVehicleForOrderUseCase` (zero-click
auto-assignment, stage 1) — mocked repositories, no database required.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from lpg.application.delivery.auto_assignment import (
    SuggestDriverAndVehicleForOrderQuery,
    SuggestDriverAndVehicleForOrderUseCase,
)
from lpg.domain.delivery.driver import Driver
from lpg.domain.delivery.route import Route
from lpg.domain.delivery.vehicle import Vehicle
from lpg.domain.order.order import DeliveryAddress, Order, OrderLine


def _make_order(**kwargs: object) -> Order:
    defaults: dict[str, object] = {
        "order_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "branch_id": uuid.uuid4(),
        "customer_id": uuid.uuid4(),
        "address_id": uuid.uuid4(),
        "delivery_address": DeliveryAddress(address_line="1 Test Street"),
        "booking_source": "staff",
        "requested_date": datetime.now(UTC),
        "lines": [
            OrderLine(line_id=uuid.uuid4(), cylinder_type_id=uuid.uuid4(), quantity_ordered=4)
        ],
    }
    defaults.update(kwargs)
    return Order(**defaults)  # type: ignore[arg-type]


def _make_driver(**kwargs: object) -> Driver:
    defaults: dict[str, object] = {
        "driver_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "branch_id": uuid.uuid4(),
        "employee_id": uuid.uuid4(),
        "license_number": "DL-1234567890",
    }
    defaults.update(kwargs)
    return Driver(**defaults)  # type: ignore[arg-type]


def _make_vehicle(**kwargs: object) -> Vehicle:
    defaults: dict[str, object] = {
        "vehicle_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "branch_id": uuid.uuid4(),
        "registration_number": "TN-01-AB-1234",
        "make": "Tata",
        "model": "Ace",
        "capacity_units": 50,
    }
    defaults.update(kwargs)
    return Vehicle(**defaults)  # type: ignore[arg-type]


def _make_route(**kwargs: object) -> Route:
    defaults: dict[str, object] = {
        "route_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "branch_id": uuid.uuid4(),
        "driver_id": uuid.uuid4(),
        "vehicle_id": uuid.uuid4(),
    }
    defaults.update(kwargs)
    return Route(**defaults)  # type: ignore[arg-type]


@pytest.fixture
def mock_order_repo() -> MagicMock:
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_driver_repo() -> MagicMock:
    repo = MagicMock()
    repo.list_drivers = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_vehicle_repo() -> MagicMock:
    repo = MagicMock()
    repo.list_vehicles = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_route_repo() -> MagicMock:
    repo = MagicMock()
    repo.get_active_route_for_driver = AsyncMock(return_value=None)
    repo.get_active_route_for_vehicle = AsyncMock(return_value=None)
    repo.list_routes = AsyncMock(return_value=[])
    return repo


def _use_case(
    mock_order_repo: MagicMock,
    mock_driver_repo: MagicMock,
    mock_vehicle_repo: MagicMock,
    mock_route_repo: MagicMock,
) -> SuggestDriverAndVehicleForOrderUseCase:
    return SuggestDriverAndVehicleForOrderUseCase(
        mock_order_repo, mock_driver_repo, mock_vehicle_repo, mock_route_repo
    )


class TestSuggestDriverAndVehicleForOrderUseCase:
    async def test_no_order_returns_none(
        self,
        mock_order_repo: MagicMock,
        mock_driver_repo: MagicMock,
        mock_vehicle_repo: MagicMock,
        mock_route_repo: MagicMock,
    ) -> None:
        mock_order_repo.get_by_id = AsyncMock(return_value=None)
        use_case = _use_case(mock_order_repo, mock_driver_repo, mock_vehicle_repo, mock_route_repo)

        result = await use_case.execute(
            SuggestDriverAndVehicleForOrderQuery(order_id=uuid.uuid4())
        )

        assert result is None

    async def test_empty_branch_returns_none(
        self,
        mock_order_repo: MagicMock,
        mock_driver_repo: MagicMock,
        mock_vehicle_repo: MagicMock,
        mock_route_repo: MagicMock,
    ) -> None:
        order = _make_order()
        mock_order_repo.get_by_id = AsyncMock(return_value=order)
        mock_driver_repo.list_drivers = AsyncMock(return_value=[])

        use_case = _use_case(mock_order_repo, mock_driver_repo, mock_vehicle_repo, mock_route_repo)
        result = await use_case.execute(SuggestDriverAndVehicleForOrderQuery(order_id=order.id))

        assert result is None

    async def test_all_drivers_busy_returns_none(
        self,
        mock_order_repo: MagicMock,
        mock_driver_repo: MagicMock,
        mock_vehicle_repo: MagicMock,
        mock_route_repo: MagicMock,
    ) -> None:
        order = _make_order()
        driver = _make_driver(branch_id=order.branch_id)
        busy_route = _make_route(branch_id=order.branch_id, driver_id=driver.id)
        mock_order_repo.get_by_id = AsyncMock(return_value=order)
        mock_driver_repo.list_drivers = AsyncMock(return_value=[driver])
        mock_route_repo.get_active_route_for_driver = AsyncMock(return_value=busy_route)

        use_case = _use_case(mock_order_repo, mock_driver_repo, mock_vehicle_repo, mock_route_repo)
        result = await use_case.execute(SuggestDriverAndVehicleForOrderQuery(order_id=order.id))

        assert result is None

    async def test_no_eligible_vehicle_returns_none_even_with_an_idle_driver(
        self,
        mock_order_repo: MagicMock,
        mock_driver_repo: MagicMock,
        mock_vehicle_repo: MagicMock,
        mock_route_repo: MagicMock,
    ) -> None:
        order = _make_order()
        driver = _make_driver(branch_id=order.branch_id)
        mock_order_repo.get_by_id = AsyncMock(return_value=order)
        mock_driver_repo.list_drivers = AsyncMock(return_value=[driver])
        mock_vehicle_repo.list_vehicles = AsyncMock(return_value=[])
        mock_route_repo.get_active_route_for_driver = AsyncMock(return_value=None)

        use_case = _use_case(mock_order_repo, mock_driver_repo, mock_vehicle_repo, mock_route_repo)
        result = await use_case.execute(SuggestDriverAndVehicleForOrderQuery(order_id=order.id))

        assert result is None

    async def test_single_idle_driver_and_vehicle_suggested(
        self,
        mock_order_repo: MagicMock,
        mock_driver_repo: MagicMock,
        mock_vehicle_repo: MagicMock,
        mock_route_repo: MagicMock,
    ) -> None:
        order = _make_order()
        driver = _make_driver(branch_id=order.branch_id)
        vehicle = _make_vehicle(branch_id=order.branch_id)
        mock_order_repo.get_by_id = AsyncMock(return_value=order)
        mock_driver_repo.list_drivers = AsyncMock(return_value=[driver])
        mock_vehicle_repo.list_vehicles = AsyncMock(return_value=[vehicle])
        mock_route_repo.get_active_route_for_driver = AsyncMock(return_value=None)
        mock_route_repo.get_active_route_for_vehicle = AsyncMock(return_value=None)

        use_case = _use_case(mock_order_repo, mock_driver_repo, mock_vehicle_repo, mock_route_repo)
        result = await use_case.execute(SuggestDriverAndVehicleForOrderQuery(order_id=order.id))

        assert result is not None
        assert result.driver_id == driver.id
        assert result.vehicle_id == vehicle.id
        assert result.reasons

    async def test_wrong_branch_driver_and_vehicle_excluded(
        self,
        mock_order_repo: MagicMock,
        mock_driver_repo: MagicMock,
        mock_vehicle_repo: MagicMock,
        mock_route_repo: MagicMock,
    ) -> None:
        order = _make_order()
        # `list_drivers`/`list_vehicles` are called with `branch_id=order.
        # branch_id` in production — the fakes here return whatever's
        # configured regardless of the arg, so simulate the *filtered*
        # repository behavior directly: nothing from another branch is
        # ever returned in the first place.
        mock_order_repo.get_by_id = AsyncMock(return_value=order)
        mock_driver_repo.list_drivers = AsyncMock(return_value=[])
        mock_vehicle_repo.list_vehicles = AsyncMock(return_value=[])

        use_case = _use_case(mock_order_repo, mock_driver_repo, mock_vehicle_repo, mock_route_repo)
        result = await use_case.execute(SuggestDriverAndVehicleForOrderQuery(order_id=order.id))

        assert result is None
        mock_driver_repo.list_drivers.assert_called_once_with(
            status="active", branch_id=order.branch_id, limit=200
        )
        # No eligible driver -> the use case short-circuits before ever
        # looking up vehicles, avoiding a wasted query.
        mock_vehicle_repo.list_vehicles.assert_not_called()

    async def test_load_balances_to_the_driver_with_fewer_active_stops_today(
        self,
        mock_order_repo: MagicMock,
        mock_driver_repo: MagicMock,
        mock_vehicle_repo: MagicMock,
        mock_route_repo: MagicMock,
    ) -> None:
        order = _make_order()
        busy_driver = _make_driver(branch_id=order.branch_id)
        idle_driver = _make_driver(branch_id=order.branch_id)
        vehicle = _make_vehicle(branch_id=order.branch_id)

        # Both drivers are "idle" in the get_active_route_for_driver sense
        # (no *currently open* route) but one already has two stops
        # scheduled for today via a route that happens to be `completed`
        # (so it doesn't count as "active" for the idleness check) —
        # simpler: give one driver a route with 2 non-terminal stops via
        # `list_routes`, matching the tiebreak query's own data source.
        loaded_route = _make_route(branch_id=order.branch_id, driver_id=busy_driver.id)
        loaded_route.record_planned()
        loaded_route.assign_order(uuid.uuid4())
        loaded_route.assign_order(uuid.uuid4())

        mock_order_repo.get_by_id = AsyncMock(return_value=order)
        mock_driver_repo.list_drivers = AsyncMock(return_value=[busy_driver, idle_driver])
        mock_vehicle_repo.list_vehicles = AsyncMock(return_value=[vehicle])
        mock_route_repo.get_active_route_for_driver = AsyncMock(return_value=None)
        mock_route_repo.get_active_route_for_vehicle = AsyncMock(return_value=None)
        mock_route_repo.list_routes = AsyncMock(return_value=[loaded_route])

        use_case = _use_case(mock_order_repo, mock_driver_repo, mock_vehicle_repo, mock_route_repo)
        result = await use_case.execute(SuggestDriverAndVehicleForOrderQuery(order_id=order.id))

        assert result is not None
        assert result.driver_id == idle_driver.id

    async def test_largest_capacity_vehicle_preferred_among_idle_candidates(
        self,
        mock_order_repo: MagicMock,
        mock_driver_repo: MagicMock,
        mock_vehicle_repo: MagicMock,
        mock_route_repo: MagicMock,
    ) -> None:
        order = _make_order()
        driver = _make_driver(branch_id=order.branch_id)
        small_vehicle = _make_vehicle(branch_id=order.branch_id, capacity_units=20)
        large_vehicle = _make_vehicle(branch_id=order.branch_id, capacity_units=80)
        mock_order_repo.get_by_id = AsyncMock(return_value=order)
        mock_driver_repo.list_drivers = AsyncMock(return_value=[driver])
        mock_vehicle_repo.list_vehicles = AsyncMock(return_value=[small_vehicle, large_vehicle])
        mock_route_repo.get_active_route_for_driver = AsyncMock(return_value=None)
        mock_route_repo.get_active_route_for_vehicle = AsyncMock(return_value=None)

        use_case = _use_case(mock_order_repo, mock_driver_repo, mock_vehicle_repo, mock_route_repo)
        result = await use_case.execute(SuggestDriverAndVehicleForOrderQuery(order_id=order.id))

        assert result is not None
        assert result.vehicle_id == large_vehicle.id
