"""Unit tests for `LoadAndDispatchRouteUseCase` — the Dispatch Board's
one-step trip sheet. Mocked repositories and UoW, same shape as
`test_route_use_cases.py`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from lpg.application.common.errors import (
    ConflictError,
    DuplicateRouteAssignmentError,
    ValidationError,
    WeighmentCheckRequiredError,
)
from lpg.application.delivery.use_cases import (
    AssignOrderToRouteCommand,
    AssignOrderToRouteUseCase,
    LoadAndDispatchRouteCommand,
    LoadAndDispatchRouteUseCase,
    LoadVehicleLine,
)
from lpg.domain.delivery.route import LoadedLine, Route
from lpg.domain.inventory.inventory_location import InsufficientStockError, InventoryLocation
from lpg.domain.order.order import DeliveryAddress, Order, OrderLine
from lpg.domain.tenant.tenant_configuration import TenantConfiguration

CYLINDER = uuid.uuid4()


def _route(status: str = "planned") -> Route:
    return Route(
        route_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        driver_id=uuid.uuid4(),
        vehicle_id=uuid.uuid4(),
        status=status,
    )


def _confirmed_order(quantity: int = 3, cylinder_type_id: uuid.UUID = CYLINDER) -> Order:
    order = Order(
        order_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        address_id=uuid.uuid4(),
        delivery_address=DeliveryAddress(address_line="1 Test Street"),
        booking_source="staff",
        requested_date=datetime.now(UTC),
        order_number="ORD000006",
        lines=[
            OrderLine(
                line_id=uuid.uuid4(), cylinder_type_id=cylinder_type_id, quantity_ordered=quantity
            )
        ],
    )
    order.submit(changed_by=uuid.uuid4())
    order.confirm(unit_prices={cylinder_type_id: Decimal("900")}, changed_by=uuid.uuid4())
    return order


class _World:
    """One route, one warehouse, one van, and the orders the repos can see."""

    def __init__(self, route: Route, *, warehouse_stock: int = 50, van_stock: int = 0) -> None:
        self.route = route
        self.warehouse_id = uuid.uuid4()
        self.warehouse = InventoryLocation(
            inventory_location_id=uuid.uuid4(),
            tenant_id=route.tenant_id,
            location_type="warehouse",
            location_ref_id=self.warehouse_id,
            balances={(CYLINDER, "filled"): warehouse_stock} if warehouse_stock else {},
        )
        self.van = InventoryLocation(
            inventory_location_id=uuid.uuid4(),
            tenant_id=route.tenant_id,
            location_type="vehicle",
            location_ref_id=route.vehicle_id,
            balances={(CYLINDER, "filled"): van_stock} if van_stock else {},
        )
        self.orders: dict[uuid.UUID, Order] = {}

        self.route_repo = MagicMock()
        self.route_repo.get_by_id = AsyncMock(return_value=route)
        self.route_repo.save = AsyncMock()
        self.route_repo.count_active_routes_for_order = AsyncMock(return_value=0)
        self.order_repo = MagicMock()
        self.order_repo.get_by_id = AsyncMock(side_effect=lambda oid: self.orders.get(oid))
        self.order_repo.save = AsyncMock()
        self.inventory_repo = MagicMock()
        self.inventory_repo.save = AsyncMock()
        self.inventory_repo.next_id = MagicMock(side_effect=uuid.uuid4)

        async def _by_ref(location_type: str, _ref: uuid.UUID) -> InventoryLocation:
            return self.warehouse if location_type == "warehouse" else self.van

        self.inventory_repo.get_by_location_ref = AsyncMock(side_effect=_by_ref)
        self.uow = MagicMock()
        self.uow.commit = AsyncMock()

    def add(self, order: Order) -> Order:
        self.orders[order.id] = order
        return order

    def use_case(self, **kwargs: MagicMock) -> LoadAndDispatchRouteUseCase:
        return LoadAndDispatchRouteUseCase(
            self.route_repo, self.order_repo, self.inventory_repo, self.uow, **kwargs
        )

    def command(self, order_ids: list[uuid.UUID], extra: int = 0) -> LoadAndDispatchRouteCommand:
        return LoadAndDispatchRouteCommand(
            route_id=self.route.id,
            warehouse_id=self.warehouse_id,
            order_ids=order_ids,
            extra_lines=[LoadVehicleLine(cylinder_type_id=CYLINDER, quantity=extra)]
            if extra
            else [],
            performed_by=uuid.uuid4(),
        )

    def assert_nothing_saved(self) -> None:
        self.route_repo.save.assert_not_called()
        self.order_repo.save.assert_not_called()
        self.inventory_repo.save.assert_not_called()
        self.uow.commit.assert_not_called()


def _manifest(route: Route) -> list[tuple[uuid.UUID, int]]:
    return [(line.cylinder_type_id, line.quantity) for line in route.loaded_lines]


class TestLoadAndDispatchRoute:
    async def test_loads_what_the_orders_need_and_releases_them_to_the_driver(self) -> None:
        world = _World(_route())
        first, second = world.add(_confirmed_order(3)), world.add(_confirmed_order(2))

        route = await world.use_case().execute(world.command([first.id, second.id]))

        assert route.status == "loaded"
        assert _manifest(route) == [(CYLINDER, 5)]
        assert [stop.order_id for stop in route.stops] == [first.id, second.id]
        assert world.warehouse.balance_of(CYLINDER, "filled") == 45
        # Every loaded cylinder is reserved for an order — none left free.
        assert world.van.balance_of(CYLINDER, "filled") == 0
        for order in (first, second):
            assert order.status == "ready_for_dispatch"
            assert order.lines[0].quantity_pending == 0
        assert world.order_repo.save.call_count == 2
        world.uow.commit.assert_called_once()

    async def test_spares_ride_along_unreserved(self) -> None:
        world = _World(_route())
        order = world.add(_confirmed_order(3))

        route = await world.use_case().execute(world.command([order.id], extra=2))

        assert _manifest(route) == [(CYLINDER, 5)]
        assert world.van.balance_of(CYLINDER, "filled") == 2

    async def test_free_stock_already_on_the_van_is_used_first(self) -> None:
        world = _World(_route(), van_stock=2)
        order = world.add(_confirmed_order(3))

        route = await world.use_case().execute(world.command([order.id]))

        # Only 1 was loaded, but the driver checks the whole van: the 2 that
        # were already on it are part of this trip's manifest (DR-04).
        assert _manifest(route) == [(CYLINDER, 3)]
        assert world.warehouse.balance_of(CYLINDER, "filled") == 49
        assert order.status == "ready_for_dispatch"

    async def test_reserves_orders_added_before_the_van_was_loaded(self) -> None:
        world = _World(_route())
        early = world.add(_confirmed_order(4))
        # The old board flow: assigned onto the empty van, so all backordered.
        await AssignOrderToRouteUseCase(
            world.route_repo, world.order_repo, world.inventory_repo, world.uow
        ).execute(
            AssignOrderToRouteCommand(
                route_id=world.route.id, order_id=early.id, changed_by=uuid.uuid4()
            )
        )
        assert early.lines[0].quantity_pending == 4

        route = await world.use_case().execute(world.command([]))

        assert route.status == "loaded"
        assert _manifest(route) == [(CYLINDER, 4)]
        assert early.status == "ready_for_dispatch"
        assert early.lines[0].quantity_pending == 0
        assert early.lines[0].is_backordered is False
        assert world.van.balance_of(CYLINDER, "filled") == 0

    async def test_reserves_orders_released_before_the_van_was_loaded(self) -> None:
        world = _World(_route())
        early = world.add(_confirmed_order(2))
        await AssignOrderToRouteUseCase(
            world.route_repo, world.order_repo, world.inventory_repo, world.uow
        ).execute(
            AssignOrderToRouteCommand(
                route_id=world.route.id, order_id=early.id, changed_by=uuid.uuid4()
            )
        )
        # The old Orders-page "Dispatch" click, before anything was loaded.
        early.dispatch(changed_by=uuid.uuid4())

        route = await world.use_case().execute(world.command([]))

        assert _manifest(route) == [(CYLINDER, 2)]
        assert early.status == "ready_for_dispatch"
        assert early.lines[0].quantity_pending == 0

    async def test_top_up_on_a_loaded_trip_adds_to_the_manifest(self) -> None:
        world = _World(_route(status="loaded"), van_stock=5)
        world.route.record_load_manifest([LoadedLine(cylinder_type_id=CYLINDER, quantity=5)])
        world.route.confirm_load(uuid.uuid4())
        order = world.add(_confirmed_order(7))

        route = await world.use_case().execute(world.command([order.id]))

        assert route.status == "loaded"
        assert _manifest(route) == [(CYLINDER, 7)]
        # The van changed since the driver checked it.
        assert route.load_confirmed_at is None
        assert order.status == "ready_for_dispatch"

    async def test_a_trip_using_only_van_stock_keeps_the_drivers_confirmation(self) -> None:
        world = _World(_route(status="loaded"), van_stock=5)
        world.route.record_load_manifest([LoadedLine(cylinder_type_id=CYLINDER, quantity=5)])
        world.route.confirm_load(uuid.uuid4())
        order = world.add(_confirmed_order(2))

        route = await world.use_case().execute(world.command([order.id]))

        assert _manifest(route) == [(CYLINDER, 5)]
        assert route.load_confirmed_at is not None

    async def test_new_stops_carry_the_order_number(self) -> None:
        world = _World(_route())
        order = world.add(_confirmed_order(1))

        route = await world.use_case().execute(world.command([order.id]))

        assert route.stops[0].order_number == "ORD000006"

    async def test_short_warehouse_moves_nothing(self) -> None:
        world = _World(_route(), warehouse_stock=1)
        order = world.add(_confirmed_order(3))

        with pytest.raises(InsufficientStockError):
            await world.use_case().execute(world.command([order.id]))

        assert world.route.status == "planned"
        assert len(world.route.stops) == 0
        assert order.status == "confirmed"
        world.assert_nothing_saved()

    async def test_a_trip_needs_at_least_one_order(self) -> None:
        world = _World(_route())

        with pytest.raises(ValidationError):
            await world.use_case().execute(world.command([]))

        world.assert_nothing_saved()

    async def test_a_trip_on_the_road_cannot_be_reloaded(self) -> None:
        world = _World(_route(status="in_progress"))
        order = world.add(_confirmed_order(1))

        with pytest.raises(ConflictError):
            await world.use_case().execute(world.command([order.id]))

        world.assert_nothing_saved()

    async def test_an_order_on_another_trip_is_refused(self) -> None:
        world = _World(_route())
        order = world.add(_confirmed_order(1))
        world.route_repo.count_active_routes_for_order.return_value = 1

        with pytest.raises(DuplicateRouteAssignmentError):
            await world.use_case().execute(world.command([order.id]))

        world.assert_nothing_saved()

    async def test_weighment_gate_still_applies(self) -> None:
        world = _World(_route())
        order = world.add(_confirmed_order(1))
        weighments = MagicMock()
        weighments.list_for_reference = AsyncMock(return_value=[])
        tenant_config = MagicMock()
        tenant_config.list_for_tenant_and_key = AsyncMock(
            return_value=[
                TenantConfiguration(
                    uuid.uuid4(),
                    uuid.uuid4(),
                    "weighment_gate_enabled",
                    True,
                    datetime.now(UTC),
                )
            ]
        )

        with pytest.raises(WeighmentCheckRequiredError):
            await world.use_case(
                weighment_record_repository=weighments, tenant_config_repository=tenant_config
            ).execute(world.command([order.id]))

        world.assert_nothing_saved()
