"""Unit tests for delivery route use cases.

Uses mocked repositories and UoW — no database required. Follows the exact
atomic-multi-aggregate pattern already proven in `test_inventory_use_cases.
py::test_load_transfer_insufficient_stock_saves_nothing`: mutate every
aggregate in memory, and if anything raises partway through, assert neither
repository's `save()` was called and `commit()` was never called.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from lpg.application.common.errors import (
    DuplicateRouteAssignmentError,
    NotFoundError,
    RouteReconciliationPendingError,
)
from lpg.application.delivery.use_cases import (
    AssignOrderToRouteCommand,
    AssignOrderToRouteUseCase,
    CompleteRouteReconciliationCommand,
    CompleteRouteReconciliationUseCase,
    ConfirmRouteLoadCommand,
    ConfirmRouteLoadUseCase,
    LoadVehicleForRouteCommand,
    LoadVehicleForRouteUseCase,
    LoadVehicleLine,
    PlanRouteCommand,
    PlanRouteUseCase,
    UpdateRouteStatusCommand,
    UpdateRouteStatusUseCase,
)
from lpg.application.inventory.ports import ReconciliationRecordEntry
from lpg.domain.common.base import InvariantViolation
from lpg.domain.delivery.route import Route, RoutePlanned
from lpg.domain.inventory.inventory_location import InsufficientStockError, InventoryLocation
from lpg.domain.order.order import DeliveryAddress, Order, OrderLine


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


def _confirmed_order(cylinder_type_id: uuid.UUID, quantity: int = 3) -> Order:
    order = _make_order(
        lines=[
            OrderLine(
                line_id=uuid.uuid4(), cylinder_type_id=cylinder_type_id, quantity_ordered=quantity
            )
        ]
    )
    order.submit(changed_by=uuid.uuid4())
    order.confirm(unit_prices={cylinder_type_id: Decimal("900")}, changed_by=uuid.uuid4())
    return order


def _make_vehicle_location(**kwargs: object) -> InventoryLocation:
    defaults: dict[str, object] = {
        "inventory_location_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "location_type": "vehicle",
        "location_ref_id": uuid.uuid4(),
    }
    defaults.update(kwargs)
    return InventoryLocation(**defaults)  # type: ignore[arg-type]


@pytest.fixture
def mock_uow() -> MagicMock:
    uow = MagicMock()
    uow.commit = AsyncMock()
    return uow


@pytest.fixture
def mock_route_repo() -> MagicMock:
    repo = MagicMock()
    repo.next_id = MagicMock(side_effect=lambda: uuid.uuid4())
    repo.save = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.count_active_routes_for_order = AsyncMock(return_value=0)
    repo.get_route_with_open_stop_for = AsyncMock(return_value=None)
    repo.get_stop_owner = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_order_repo() -> MagicMock:
    repo = MagicMock()
    repo.next_id = MagicMock(side_effect=lambda: uuid.uuid4())
    repo.save = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_inventory_repo() -> MagicMock:
    repo = MagicMock()
    repo.next_id = MagicMock(side_effect=lambda: uuid.uuid4())
    repo.save = AsyncMock()
    repo.get_by_location_ref = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_reconciliation_repo() -> MagicMock:
    repo = MagicMock()
    repo.get_latest_for_location = AsyncMock(return_value=None)
    return repo


# ==========================================================================
# PlanRouteUseCase
# ==========================================================================


class TestPlanRouteUseCase:
    async def test_creates_route_and_records_planned_event(
        self, mock_route_repo: MagicMock, mock_uow: MagicMock
    ) -> None:
        tenant_id = uuid.uuid4()
        branch_id = uuid.uuid4()
        driver_id = uuid.uuid4()
        vehicle_id = uuid.uuid4()

        use_case = PlanRouteUseCase(mock_route_repo, mock_uow)
        route = await use_case.execute(
            PlanRouteCommand(
                tenant_id=tenant_id,
                branch_id=branch_id,
                driver_id=driver_id,
                vehicle_id=vehicle_id,
            )
        )

        assert route.status == "planned"
        assert route.driver_id == driver_id
        assert route.vehicle_id == vehicle_id
        events = [e for e in route.events if isinstance(e, RoutePlanned)]
        assert len(events) == 1
        mock_route_repo.save.assert_called_once()
        mock_uow.commit.assert_called_once()


# ==========================================================================
# AssignOrderToRouteUseCase — atomicity
# ==========================================================================


class TestAssignOrderToRouteUseCase:
    async def test_full_allocation_saves_all_three_aggregates_and_commits_once(
        self,
        mock_route_repo: MagicMock,
        mock_order_repo: MagicMock,
        mock_inventory_repo: MagicMock,
        mock_uow: MagicMock,
    ) -> None:
        cylinder_type_id = uuid.uuid4()
        order = _confirmed_order(cylinder_type_id, quantity=3)
        route = _make_route(status="planned")
        vehicle_location = _make_vehicle_location(
            location_ref_id=route.vehicle_id, balances={(cylinder_type_id, "filled"): 10}
        )
        mock_route_repo.get_by_id.return_value = route
        mock_order_repo.get_by_id.return_value = order
        mock_inventory_repo.get_by_location_ref.return_value = vehicle_location

        use_case = AssignOrderToRouteUseCase(
            mock_route_repo, mock_order_repo, mock_inventory_repo, mock_uow
        )
        result = await use_case.execute(
            AssignOrderToRouteCommand(route_id=route.id, order_id=order.id, changed_by=uuid.uuid4())
        )

        assert result.order.status == "assigned"
        assert result.order.lines[0].is_backordered is False
        assert len(result.route.stops) == 1
        assert result.route.stops[0].order_id == order.id
        assert result.order.route_stop_id == result.route.stops[0].id
        assert vehicle_location.balance_of(cylinder_type_id, "filled") == 7
        mock_route_repo.save.assert_called_once()
        mock_order_repo.save.assert_called_once()
        mock_inventory_repo.save.assert_called_once()
        mock_uow.commit.assert_called_once()

    async def test_partial_stock_sets_backorder_without_raising(
        self,
        mock_route_repo: MagicMock,
        mock_order_repo: MagicMock,
        mock_inventory_repo: MagicMock,
        mock_uow: MagicMock,
    ) -> None:
        cylinder_type_id = uuid.uuid4()
        order = _confirmed_order(cylinder_type_id, quantity=5)
        route = _make_route(status="planned")
        vehicle_location = _make_vehicle_location(
            location_ref_id=route.vehicle_id, balances={(cylinder_type_id, "filled"): 2}
        )
        mock_route_repo.get_by_id.return_value = route
        mock_order_repo.get_by_id.return_value = order
        mock_inventory_repo.get_by_location_ref.return_value = vehicle_location

        use_case = AssignOrderToRouteUseCase(
            mock_route_repo, mock_order_repo, mock_inventory_repo, mock_uow
        )
        result = await use_case.execute(
            AssignOrderToRouteCommand(route_id=route.id, order_id=order.id, changed_by=uuid.uuid4())
        )

        assert result.order.lines[0].is_backordered is True
        assert result.order.lines[0].quantity_pending == 3
        assert vehicle_location.balance_of(cylinder_type_id, "filled") == 0
        mock_uow.commit.assert_called_once()

    async def test_missing_route_raises_not_found(
        self,
        mock_route_repo: MagicMock,
        mock_order_repo: MagicMock,
        mock_inventory_repo: MagicMock,
        mock_uow: MagicMock,
    ) -> None:
        use_case = AssignOrderToRouteUseCase(
            mock_route_repo, mock_order_repo, mock_inventory_repo, mock_uow
        )
        with pytest.raises(NotFoundError):
            await use_case.execute(
                AssignOrderToRouteCommand(
                    route_id=uuid.uuid4(), order_id=uuid.uuid4(), changed_by=uuid.uuid4()
                )
            )
        mock_route_repo.save.assert_not_called()
        mock_uow.commit.assert_not_called()

    async def test_missing_order_raises_not_found(
        self,
        mock_route_repo: MagicMock,
        mock_order_repo: MagicMock,
        mock_inventory_repo: MagicMock,
        mock_uow: MagicMock,
    ) -> None:
        route = _make_route()
        mock_route_repo.get_by_id.return_value = route
        use_case = AssignOrderToRouteUseCase(
            mock_route_repo, mock_order_repo, mock_inventory_repo, mock_uow
        )
        with pytest.raises(NotFoundError):
            await use_case.execute(
                AssignOrderToRouteCommand(
                    route_id=route.id, order_id=uuid.uuid4(), changed_by=uuid.uuid4()
                )
            )
        mock_order_repo.save.assert_not_called()
        mock_route_repo.save.assert_not_called()
        mock_uow.commit.assert_not_called()

    async def test_duplicate_active_route_assignment_raises_conflict_and_saves_nothing(
        self,
        mock_route_repo: MagicMock,
        mock_order_repo: MagicMock,
        mock_inventory_repo: MagicMock,
        mock_uow: MagicMock,
    ) -> None:
        route = _make_route(status="planned")
        order = _confirmed_order(uuid.uuid4())
        mock_route_repo.get_by_id.return_value = route
        mock_order_repo.get_by_id.return_value = order
        mock_route_repo.count_active_routes_for_order.return_value = 1

        use_case = AssignOrderToRouteUseCase(
            mock_route_repo, mock_order_repo, mock_inventory_repo, mock_uow
        )
        with pytest.raises(DuplicateRouteAssignmentError):
            await use_case.execute(
                AssignOrderToRouteCommand(
                    route_id=route.id, order_id=order.id, changed_by=uuid.uuid4()
                )
            )

        mock_route_repo.save.assert_not_called()
        mock_order_repo.save.assert_not_called()
        mock_inventory_repo.save.assert_not_called()
        mock_uow.commit.assert_not_called()

    async def test_atomic_failure_when_order_already_a_stop_on_this_route_saves_nothing(
        self,
        mock_route_repo: MagicMock,
        mock_order_repo: MagicMock,
        mock_inventory_repo: MagicMock,
        mock_uow: MagicMock,
    ) -> None:
        """`count_active_routes_for_order` is a *repository* query and can't
        see an order that's already a stop on *this exact* in-memory
        `Route` — `route.assign_order()` catches that itself and raises
        after `vehicle_location.reserve()` has already mutated the location
        object in memory. Nothing must be saved regardless — BR-29's "one
        transaction or none," the same guarantee
        `test_load_transfer_insufficient_stock_saves_nothing` proves for
        `LoadTransferUseCase`.
        """
        cylinder_type_id = uuid.uuid4()
        order = _confirmed_order(cylinder_type_id, quantity=2)
        route = _make_route(status="planned")
        route.assign_order(order.id)  # already a stop on this exact route

        vehicle_location = _make_vehicle_location(
            location_ref_id=route.vehicle_id, balances={(cylinder_type_id, "filled"): 10}
        )
        mock_route_repo.get_by_id.return_value = route
        mock_order_repo.get_by_id.return_value = order
        mock_inventory_repo.get_by_location_ref.return_value = vehicle_location

        use_case = AssignOrderToRouteUseCase(
            mock_route_repo, mock_order_repo, mock_inventory_repo, mock_uow
        )
        with pytest.raises(InvariantViolation, match="already assigned"):
            await use_case.execute(
                AssignOrderToRouteCommand(
                    route_id=route.id, order_id=order.id, changed_by=uuid.uuid4()
                )
            )

        mock_route_repo.save.assert_not_called()
        mock_order_repo.save.assert_not_called()
        mock_inventory_repo.save.assert_not_called()
        mock_uow.commit.assert_not_called()


# ==========================================================================
# LoadVehicleForRouteUseCase
# ==========================================================================


class TestLoadVehicleForRouteUseCase:
    async def test_transfers_stock_and_marks_route_loaded(
        self, mock_route_repo: MagicMock, mock_inventory_repo: MagicMock, mock_uow: MagicMock
    ) -> None:
        cylinder_type_id = uuid.uuid4()
        route = _make_route(status="planned")
        warehouse_id = uuid.uuid4()
        warehouse_location = InventoryLocation(
            inventory_location_id=uuid.uuid4(),
            tenant_id=route.tenant_id,
            location_type="warehouse",
            location_ref_id=warehouse_id,
            balances={(cylinder_type_id, "filled"): 50},
        )
        vehicle_location = _make_vehicle_location(location_ref_id=route.vehicle_id)

        async def _get_by_ref(location_type: str, location_ref_id: uuid.UUID) -> InventoryLocation:
            return warehouse_location if location_type == "warehouse" else vehicle_location

        mock_route_repo.get_by_id.return_value = route
        mock_inventory_repo.get_by_location_ref.side_effect = _get_by_ref

        use_case = LoadVehicleForRouteUseCase(mock_route_repo, mock_inventory_repo, mock_uow)
        result = await use_case.execute(
            LoadVehicleForRouteCommand(
                route_id=route.id,
                warehouse_id=warehouse_id,
                lines=[LoadVehicleLine(cylinder_type_id=cylinder_type_id, quantity=20)],
                performed_by=uuid.uuid4(),
            )
        )

        assert result.status == "loaded"
        assert warehouse_location.balance_of(cylinder_type_id, "filled") == 30
        assert vehicle_location.balance_of(cylinder_type_id, "filled") == 20
        assert mock_inventory_repo.save.call_count == 2
        mock_route_repo.save.assert_called_once()
        mock_uow.commit.assert_called_once()
        # The manifest is snapshotted for the driver's van-load check.
        assert [(ll.cylinder_type_id, ll.quantity) for ll in result.loaded_lines] == [
            (cylinder_type_id, 20)
        ]

    async def test_missing_route_raises_not_found(
        self, mock_route_repo: MagicMock, mock_inventory_repo: MagicMock, mock_uow: MagicMock
    ) -> None:
        use_case = LoadVehicleForRouteUseCase(mock_route_repo, mock_inventory_repo, mock_uow)
        with pytest.raises(NotFoundError):
            await use_case.execute(
                LoadVehicleForRouteCommand(
                    route_id=uuid.uuid4(),
                    warehouse_id=uuid.uuid4(),
                    lines=[LoadVehicleLine(cylinder_type_id=uuid.uuid4(), quantity=1)],
                    performed_by=uuid.uuid4(),
                )
            )
        mock_route_repo.save.assert_not_called()
        mock_uow.commit.assert_not_called()

    async def test_insufficient_warehouse_stock_saves_nothing(
        self, mock_route_repo: MagicMock, mock_inventory_repo: MagicMock, mock_uow: MagicMock
    ) -> None:
        cylinder_type_id = uuid.uuid4()
        route = _make_route(status="planned")
        warehouse_id = uuid.uuid4()
        warehouse_location = InventoryLocation(
            inventory_location_id=uuid.uuid4(),
            tenant_id=route.tenant_id,
            location_type="warehouse",
            location_ref_id=warehouse_id,
        )
        vehicle_location = _make_vehicle_location(location_ref_id=route.vehicle_id)

        async def _get_by_ref(location_type: str, location_ref_id: uuid.UUID) -> InventoryLocation:
            return warehouse_location if location_type == "warehouse" else vehicle_location

        mock_route_repo.get_by_id.return_value = route
        mock_inventory_repo.get_by_location_ref.side_effect = _get_by_ref

        use_case = LoadVehicleForRouteUseCase(mock_route_repo, mock_inventory_repo, mock_uow)
        with pytest.raises(InsufficientStockError):
            await use_case.execute(
                LoadVehicleForRouteCommand(
                    route_id=route.id,
                    warehouse_id=warehouse_id,
                    lines=[LoadVehicleLine(cylinder_type_id=cylinder_type_id, quantity=999)],
                    performed_by=uuid.uuid4(),
                )
            )

        assert route.status == "planned"
        assert vehicle_location.balances == {}
        mock_inventory_repo.save.assert_not_called()
        mock_route_repo.save.assert_not_called()
        mock_uow.commit.assert_not_called()


# ==========================================================================
# CompleteRouteReconciliationUseCase
# ==========================================================================


class TestCompleteRouteReconciliationUseCase:
    def _approved_record(
        self, *, location_id: uuid.UUID, approved_by: uuid.UUID | None
    ) -> ReconciliationRecordEntry:
        return ReconciliationRecordEntry(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            inventory_location_id=location_id,
            cylinder_type_id=uuid.uuid4(),
            status="filled",
            expected_quantity=10,
            actual_quantity=10,
            variance=0,
            recorded_by=uuid.uuid4(),
            approved_by=approved_by,
            approved_at=datetime.now(UTC) if approved_by is not None else None,
        )

    async def test_completes_when_reconciliation_approved(
        self,
        mock_route_repo: MagicMock,
        mock_inventory_repo: MagicMock,
        mock_reconciliation_repo: MagicMock,
        mock_uow: MagicMock,
    ) -> None:
        route = _make_route(status="completed")
        vehicle_location = _make_vehicle_location(location_ref_id=route.vehicle_id)
        mock_route_repo.get_by_id.return_value = route
        mock_inventory_repo.get_by_location_ref.return_value = vehicle_location
        mock_reconciliation_repo.get_latest_for_location.return_value = self._approved_record(
            location_id=vehicle_location.id, approved_by=uuid.uuid4()
        )

        use_case = CompleteRouteReconciliationUseCase(
            mock_route_repo, mock_inventory_repo, mock_reconciliation_repo, mock_uow
        )
        result = await use_case.execute(CompleteRouteReconciliationCommand(route_id=route.id))

        assert result.status == "reconciled"
        mock_route_repo.save.assert_called_once()
        mock_uow.commit.assert_called_once()

    async def test_missing_route_raises_not_found(
        self,
        mock_route_repo: MagicMock,
        mock_inventory_repo: MagicMock,
        mock_reconciliation_repo: MagicMock,
        mock_uow: MagicMock,
    ) -> None:
        use_case = CompleteRouteReconciliationUseCase(
            mock_route_repo, mock_inventory_repo, mock_reconciliation_repo, mock_uow
        )
        with pytest.raises(NotFoundError):
            await use_case.execute(CompleteRouteReconciliationCommand(route_id=uuid.uuid4()))
        mock_route_repo.save.assert_not_called()
        mock_uow.commit.assert_not_called()

    async def test_raises_pending_when_no_reconciliation_record_exists(
        self,
        mock_route_repo: MagicMock,
        mock_inventory_repo: MagicMock,
        mock_reconciliation_repo: MagicMock,
        mock_uow: MagicMock,
    ) -> None:
        route = _make_route(status="completed")
        vehicle_location = _make_vehicle_location(location_ref_id=route.vehicle_id)
        mock_route_repo.get_by_id.return_value = route
        mock_inventory_repo.get_by_location_ref.return_value = vehicle_location
        mock_reconciliation_repo.get_latest_for_location.return_value = None

        use_case = CompleteRouteReconciliationUseCase(
            mock_route_repo, mock_inventory_repo, mock_reconciliation_repo, mock_uow
        )
        with pytest.raises(RouteReconciliationPendingError):
            await use_case.execute(CompleteRouteReconciliationCommand(route_id=route.id))

        mock_route_repo.save.assert_not_called()
        mock_uow.commit.assert_not_called()

    async def test_raises_pending_when_reconciliation_not_yet_approved(
        self,
        mock_route_repo: MagicMock,
        mock_inventory_repo: MagicMock,
        mock_reconciliation_repo: MagicMock,
        mock_uow: MagicMock,
    ) -> None:
        route = _make_route(status="completed")
        vehicle_location = _make_vehicle_location(location_ref_id=route.vehicle_id)
        mock_route_repo.get_by_id.return_value = route
        mock_inventory_repo.get_by_location_ref.return_value = vehicle_location
        mock_reconciliation_repo.get_latest_for_location.return_value = self._approved_record(
            location_id=vehicle_location.id, approved_by=None
        )

        use_case = CompleteRouteReconciliationUseCase(
            mock_route_repo, mock_inventory_repo, mock_reconciliation_repo, mock_uow
        )
        with pytest.raises(RouteReconciliationPendingError):
            await use_case.execute(CompleteRouteReconciliationCommand(route_id=route.id))

        mock_route_repo.save.assert_not_called()
        mock_uow.commit.assert_not_called()

    async def test_raises_pending_when_vehicle_has_no_inventory_location_at_all(
        self,
        mock_route_repo: MagicMock,
        mock_inventory_repo: MagicMock,
        mock_reconciliation_repo: MagicMock,
        mock_uow: MagicMock,
    ) -> None:
        route = _make_route(status="completed")
        mock_route_repo.get_by_id.return_value = route
        mock_inventory_repo.get_by_location_ref.return_value = None

        use_case = CompleteRouteReconciliationUseCase(
            mock_route_repo, mock_inventory_repo, mock_reconciliation_repo, mock_uow
        )
        with pytest.raises(RouteReconciliationPendingError):
            await use_case.execute(CompleteRouteReconciliationCommand(route_id=route.id))

        mock_reconciliation_repo.get_latest_for_location.assert_not_called()
        mock_route_repo.save.assert_not_called()
        mock_uow.commit.assert_not_called()


# ==========================================================================
# UpdateRouteStatusUseCase
# ==========================================================================


class TestUpdateRouteStatusUseCase:
    async def test_transitions_loaded_to_in_progress(
        self, mock_route_repo: MagicMock, mock_uow: MagicMock
    ) -> None:
        route = _make_route(status="loaded")
        mock_route_repo.get_by_id.return_value = route
        use_case = UpdateRouteStatusUseCase(mock_route_repo, mock_uow)

        result = await use_case.execute(
            UpdateRouteStatusCommand(route_id=route.id, new_status="in_progress")
        )

        assert result.status == "in_progress"
        mock_route_repo.save.assert_called_once()
        mock_uow.commit.assert_called_once()

    async def test_transitions_planned_to_cancelled(
        self, mock_route_repo: MagicMock, mock_uow: MagicMock
    ) -> None:
        route = _make_route(status="planned")
        mock_route_repo.get_by_id.return_value = route
        use_case = UpdateRouteStatusUseCase(mock_route_repo, mock_uow)

        result = await use_case.execute(
            UpdateRouteStatusCommand(route_id=route.id, new_status="cancelled")
        )

        assert result.status == "cancelled"

    async def test_missing_route_raises_not_found(
        self, mock_route_repo: MagicMock, mock_uow: MagicMock
    ) -> None:
        use_case = UpdateRouteStatusUseCase(mock_route_repo, mock_uow)
        with pytest.raises(NotFoundError):
            await use_case.execute(
                UpdateRouteStatusCommand(route_id=uuid.uuid4(), new_status="cancelled")
            )
        mock_route_repo.save.assert_not_called()
        mock_uow.commit.assert_not_called()

    async def test_illegal_transition_saves_nothing(
        self, mock_route_repo: MagicMock, mock_uow: MagicMock
    ) -> None:
        route = _make_route(status="reconciled")
        mock_route_repo.get_by_id.return_value = route
        use_case = UpdateRouteStatusUseCase(mock_route_repo, mock_uow)

        with pytest.raises(InvariantViolation):
            await use_case.execute(
                UpdateRouteStatusCommand(route_id=route.id, new_status="cancelled")
            )

        mock_route_repo.save.assert_not_called()
        mock_uow.commit.assert_not_called()


# ==========================================================================
# ConfirmRouteLoadUseCase
# ==========================================================================


class TestConfirmRouteLoadUseCase:
    async def test_confirms_and_persists(
        self, mock_route_repo: MagicMock, mock_uow: MagicMock
    ) -> None:
        route = _make_route(status="loaded")
        mock_route_repo.get_by_id.return_value = route
        use_case = ConfirmRouteLoadUseCase(mock_route_repo, mock_uow)

        result = await use_case.execute(
            ConfirmRouteLoadCommand(route_id=route.id, confirmed_by=uuid.uuid4())
        )

        assert result.load_confirmed_at is not None
        mock_route_repo.save.assert_called_once()
        mock_uow.commit.assert_called_once()

    async def test_missing_route_raises_not_found(
        self, mock_route_repo: MagicMock, mock_uow: MagicMock
    ) -> None:
        mock_route_repo.get_by_id.return_value = None
        use_case = ConfirmRouteLoadUseCase(mock_route_repo, mock_uow)
        with pytest.raises(NotFoundError):
            await use_case.execute(
                ConfirmRouteLoadCommand(route_id=uuid.uuid4(), confirmed_by=uuid.uuid4())
            )

    async def test_another_drivers_route_is_not_found(
        self, mock_route_repo: MagicMock, mock_uow: MagicMock
    ) -> None:
        route = _make_route(status="loaded")
        mock_route_repo.get_by_id.return_value = route
        use_case = ConfirmRouteLoadUseCase(mock_route_repo, mock_uow)
        with pytest.raises(NotFoundError):
            await use_case.execute(
                ConfirmRouteLoadCommand(
                    route_id=route.id,
                    confirmed_by=uuid.uuid4(),
                    expected_driver_id=uuid.uuid4(),
                )
            )
        mock_route_repo.save.assert_not_called()

    async def test_rejected_before_loaded(
        self, mock_route_repo: MagicMock, mock_uow: MagicMock
    ) -> None:
        route = _make_route(status="planned")
        mock_route_repo.get_by_id.return_value = route
        use_case = ConfirmRouteLoadUseCase(mock_route_repo, mock_uow)
        with pytest.raises(InvariantViolation):
            await use_case.execute(
                ConfirmRouteLoadCommand(route_id=route.id, confirmed_by=uuid.uuid4())
            )
        mock_route_repo.save.assert_not_called()
        mock_uow.commit.assert_not_called()
