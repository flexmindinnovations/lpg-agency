"""Unit tests for order use cases.

Uses mocked repositories/ports and UoW — no database required. Phase 12
threaded a `route_repository` through `AssignOrderUseCase`/
`DeliverOrderUseCase`/`CancelOrderUseCase`/`RescheduleOrderUseCase` (and, at
the integration level only, `DepartOrderUseCase`/
`RecordFailedDeliveryUseCase`/`ApproveOrderCancellationUseCase`) — every
helper below that builds an order past `confirmed` now also builds the
paired `Route`/`RouteStop` the way `AssignOrderToRouteUseCase` itself would,
and wires `mock_route_repo.get_stop_owner`/`get_by_id` to resolve it,
mirroring `test_route_use_cases.py`'s own fixtures.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable
    from contextlib import AbstractAsyncContextManager

from lpg.application.common.errors import (
    IncompletePodError,
    NotFoundError,
    OtpMismatchError,
)
from lpg.application.delivery.ports import RouteStopOwner
from lpg.application.order.ports import CancellationRecordEntry, ProofOfDeliveryEntry
from lpg.application.order.use_cases import (
    AssignOrderCommand,
    AssignOrderUseCase,
    BulkCancelOrdersCommand,
    BulkCancelOrdersUseCase,
    CancelOrderCommand,
    CancelOrderUseCase,
    ConfirmOrderCommand,
    ConfirmOrderUseCase,
    DeliverOrderCommand,
    DeliverOrderUseCase,
    RescheduleOrderCommand,
    RescheduleOrderUseCase,
)
from lpg.domain.customer.customer import Customer
from lpg.domain.delivery.route import Route, RoutePlanned
from lpg.domain.inventory.inventory_location import InventoryLocation
from lpg.domain.order.order import (
    DeliveredLine,
    DeliveryAddress,
    InsufficientVehicleStockError,
    Order,
    OrderLine,
)
from lpg.domain.tenant.price_list import PriceListEntry


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


def _make_customer(**kwargs: object) -> Customer:
    defaults: dict[str, object] = {
        "customer_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "branch_id": uuid.uuid4(),
        "consumer_number": "CN-000001",
        "full_name": "Test Customer",
        "phone_number": "+919876543210",
    }
    defaults.update(kwargs)
    return Customer(**defaults)  # type: ignore[arg-type]


def _make_vehicle_location(**kwargs: object) -> InventoryLocation:
    defaults: dict[str, object] = {
        "inventory_location_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "location_type": "vehicle",
        "location_ref_id": uuid.uuid4(),
    }
    defaults.update(kwargs)
    return InventoryLocation(**defaults)  # type: ignore[arg-type]


def _make_route(**kwargs: object) -> Route:
    defaults: dict[str, object] = {
        "route_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "branch_id": uuid.uuid4(),
        "driver_id": uuid.uuid4(),
        "vehicle_id": uuid.uuid4(),
        "status": "planned",
    }
    defaults.update(kwargs)
    return Route(**defaults)  # type: ignore[arg-type]


def _assigned_order_with_route(
    cylinder_type_id: uuid.UUID, reserved: int = 4
) -> tuple[Order, Route]:
    """A `confirmed -> assigned` order paired with the `Route`/`RouteStop`
    that produced its `route_stop_id` — the shape `AssignOrderToRouteUseCase`
    itself creates, needed by any use case that resolves a route stop's
    owning route via `RouteRepository.get_stop_owner()`.
    """
    order = _make_order(
        lines=[
            OrderLine(
                line_id=uuid.uuid4(), cylinder_type_id=cylinder_type_id, quantity_ordered=reserved
            )
        ]
    )
    order.submit(changed_by=uuid.uuid4())
    order.confirm(unit_prices={cylinder_type_id: Decimal("900")}, changed_by=uuid.uuid4())

    route = _make_route(tenant_id=order.tenant_id, branch_id=order.branch_id, status="planned")
    route.assign_order(order.id)
    stop = route.stops[0]

    order.assign(
        route_stop_id=stop.id,
        reservations={cylinder_type_id: reserved},
        backorders={cylinder_type_id: 0},
        changed_by=uuid.uuid4(),
    )
    return order, route


@pytest.fixture
def mock_uow() -> MagicMock:
    uow = MagicMock()
    uow.commit = AsyncMock()
    return uow


@pytest.fixture
def mock_order_repo() -> MagicMock:
    repo = MagicMock()
    repo.next_id = MagicMock(side_effect=lambda: uuid.uuid4())
    repo.save = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_route_repo() -> MagicMock:
    repo = MagicMock()
    repo.next_id = MagicMock(side_effect=lambda: uuid.uuid4())
    repo.save = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.get_route_with_open_stop_for = AsyncMock(return_value=None)
    repo.count_active_routes_for_order = AsyncMock(return_value=0)
    repo.get_stop_owner = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_inventory_repo() -> MagicMock:
    repo = MagicMock()
    repo.save = AsyncMock()
    repo.get_by_location_ref = AsyncMock(return_value=None)
    return repo


def _stub_route_lookup(mock_route_repo: MagicMock, route: Route) -> None:
    """Wires `get_stop_owner`/`get_by_id` to resolve a single, already-built
    `route` — the pattern `DeliverOrderUseCase`/`CancelOrderUseCase` use to
    go from an order's `route_stop_id` to its owning `Route`.
    """
    mock_route_repo.get_stop_owner.return_value = RouteStopOwner(
        route_id=route.id, driver_id=route.driver_id, vehicle_id=route.vehicle_id
    )
    mock_route_repo.get_by_id.return_value = route


class TestAssignOrderUseCase:
    async def test_full_allocation_saves_route_order_and_inventory_and_commits_once(
        self,
        mock_order_repo: MagicMock,
        mock_route_repo: MagicMock,
        mock_inventory_repo: MagicMock,
        mock_uow: MagicMock,
    ) -> None:
        cylinder_type_id = uuid.uuid4()
        order = _make_order(
            lines=[
                OrderLine(
                    line_id=uuid.uuid4(), cylinder_type_id=cylinder_type_id, quantity_ordered=3
                )
            ]
        )
        order.submit(changed_by=uuid.uuid4())
        order.confirm(unit_prices={cylinder_type_id: Decimal("900")}, changed_by=uuid.uuid4())
        mock_order_repo.get_by_id.return_value = order

        driver_id = uuid.uuid4()
        vehicle_id = uuid.uuid4()
        route = _make_route(
            tenant_id=order.tenant_id,
            branch_id=order.branch_id,
            driver_id=driver_id,
            vehicle_id=vehicle_id,
        )
        mock_route_repo.get_route_with_open_stop_for.return_value = route
        mock_route_repo.get_by_id.return_value = route

        vehicle_location = _make_vehicle_location(
            location_ref_id=vehicle_id, balances={(cylinder_type_id, "filled"): 10}
        )
        mock_inventory_repo.get_by_location_ref.return_value = vehicle_location

        use_case = AssignOrderUseCase(
            mock_order_repo, mock_route_repo, mock_inventory_repo, mock_uow
        )
        result = await use_case.execute(
            AssignOrderCommand(
                order_id=order.id,
                driver_id=driver_id,
                vehicle_id=vehicle_id,
                changed_by=uuid.uuid4(),
            )
        )

        assert result.status == "assigned"
        assert result.lines[0].is_backordered is False
        assert result.route_stop_id is not None
        assert vehicle_location.balance_of(cylinder_type_id, "filled") == 7
        mock_order_repo.save.assert_called_once()
        mock_inventory_repo.save.assert_called_once()
        mock_route_repo.save.assert_called_once()
        mock_uow.commit.assert_called_once()

    async def test_partial_stock_sets_backorder_without_raising(
        self,
        mock_order_repo: MagicMock,
        mock_route_repo: MagicMock,
        mock_inventory_repo: MagicMock,
        mock_uow: MagicMock,
    ) -> None:
        cylinder_type_id = uuid.uuid4()
        order = _make_order(
            lines=[
                OrderLine(
                    line_id=uuid.uuid4(), cylinder_type_id=cylinder_type_id, quantity_ordered=5
                )
            ]
        )
        order.submit(changed_by=uuid.uuid4())
        order.confirm(unit_prices={cylinder_type_id: Decimal("900")}, changed_by=uuid.uuid4())
        mock_order_repo.get_by_id.return_value = order

        route = _make_route(tenant_id=order.tenant_id, branch_id=order.branch_id)
        mock_route_repo.get_route_with_open_stop_for.return_value = route
        mock_route_repo.get_by_id.return_value = route

        vehicle_location = _make_vehicle_location(
            location_ref_id=route.vehicle_id, balances={(cylinder_type_id, "filled"): 2}
        )
        mock_inventory_repo.get_by_location_ref.return_value = vehicle_location

        use_case = AssignOrderUseCase(
            mock_order_repo, mock_route_repo, mock_inventory_repo, mock_uow
        )
        result = await use_case.execute(
            AssignOrderCommand(
                order_id=order.id,
                driver_id=route.driver_id,
                vehicle_id=route.vehicle_id,
                changed_by=uuid.uuid4(),
            )
        )

        assert result.lines[0].is_backordered is True
        assert result.lines[0].quantity_pending == 3
        assert vehicle_location.balance_of(cylinder_type_id, "filled") == 0
        mock_uow.commit.assert_called_once()

    async def test_missing_order_raises_not_found(
        self,
        mock_order_repo: MagicMock,
        mock_route_repo: MagicMock,
        mock_inventory_repo: MagicMock,
        mock_uow: MagicMock,
    ) -> None:
        use_case = AssignOrderUseCase(
            mock_order_repo, mock_route_repo, mock_inventory_repo, mock_uow
        )
        with pytest.raises(NotFoundError):
            await use_case.execute(
                AssignOrderCommand(
                    order_id=uuid.uuid4(),
                    driver_id=uuid.uuid4(),
                    vehicle_id=uuid.uuid4(),
                    changed_by=uuid.uuid4(),
                )
            )
        mock_order_repo.save.assert_not_called()
        mock_route_repo.save.assert_not_called()
        mock_uow.commit.assert_not_called()

    async def test_creates_a_new_route_when_none_open_for_driver_vehicle_day(
        self,
        mock_order_repo: MagicMock,
        mock_route_repo: MagicMock,
        mock_inventory_repo: MagicMock,
        mock_uow: MagicMock,
    ) -> None:
        """`get_route_with_open_stop_for` finding nothing means a brand new,
        single-stop `Route` is planned and saved as part of this same call
        — exercised here with an in-memory store standing in for the real
        repository so the later `AssignOrderToRouteUseCase.get_by_id()`
        call resolves the just-created route (a mocked `save()` alone
        doesn't make `get_by_id()` see it).
        """
        cylinder_type_id = uuid.uuid4()
        order = _make_order(
            lines=[
                OrderLine(
                    line_id=uuid.uuid4(), cylinder_type_id=cylinder_type_id, quantity_ordered=2
                )
            ]
        )
        order.submit(changed_by=uuid.uuid4())
        order.confirm(unit_prices={cylinder_type_id: Decimal("900")}, changed_by=uuid.uuid4())
        mock_order_repo.get_by_id.return_value = order

        store: dict[uuid.UUID, Route] = {}

        async def _save(route: Route) -> None:
            store[route.id] = route

        async def _get_by_id(route_id: uuid.UUID) -> Route | None:
            return store.get(route_id)

        mock_route_repo.save = AsyncMock(side_effect=_save)
        mock_route_repo.get_by_id = AsyncMock(side_effect=_get_by_id)
        mock_route_repo.get_route_with_open_stop_for.return_value = None

        vehicle_location = _make_vehicle_location(balances={(cylinder_type_id, "filled"): 10})
        mock_inventory_repo.get_by_location_ref.return_value = vehicle_location

        driver_id = uuid.uuid4()
        vehicle_id = uuid.uuid4()
        use_case = AssignOrderUseCase(
            mock_order_repo, mock_route_repo, mock_inventory_repo, mock_uow
        )
        result = await use_case.execute(
            AssignOrderCommand(
                order_id=order.id,
                driver_id=driver_id,
                vehicle_id=vehicle_id,
                changed_by=uuid.uuid4(),
            )
        )

        assert result.status == "assigned"
        assert len(store) == 1
        created_route = next(iter(store.values()))
        assert created_route.driver_id == driver_id
        assert created_route.vehicle_id == vehicle_id
        assert len(created_route.stops) == 1
        assert created_route.stops[0].order_id == order.id
        planned_events = [e for e in created_route.events if isinstance(e, RoutePlanned)]
        assert len(planned_events) == 1


class TestConfirmOrderUseCase:
    async def test_confirm_snapshots_price_and_calls_stub_policies(
        self, mock_order_repo: MagicMock, mock_uow: MagicMock
    ) -> None:
        cylinder_type_id = uuid.uuid4()
        order = _make_order(
            lines=[
                OrderLine(
                    line_id=uuid.uuid4(), cylinder_type_id=cylinder_type_id, quantity_ordered=2
                )
            ]
        )
        order.submit(changed_by=uuid.uuid4())
        mock_order_repo.get_by_id.return_value = order

        customer = _make_customer(customer_id=order.customer_id)
        customer_repo = MagicMock()
        customer_repo.get_by_id = AsyncMock(return_value=customer)

        price_entry = PriceListEntry(
            entry_id=uuid.uuid4(),
            tenant_id=order.tenant_id,
            cylinder_type_id=cylinder_type_id,
            customer_type="domestic",
            price=Decimal("950.00"),
            effective_from=datetime(2020, 1, 1, tzinfo=UTC),
        )
        price_list_repo = MagicMock()
        price_list_repo.list_for_tenant_and_cylinder_type = AsyncMock(return_value=[price_entry])

        cap_policy = MagicMock()
        cap_policy.evaluate = AsyncMock()
        credit_evaluator = MagicMock()
        credit_evaluator.evaluate = AsyncMock()

        use_case = ConfirmOrderUseCase(
            mock_order_repo, customer_repo, price_list_repo, cap_policy, credit_evaluator, mock_uow
        )
        result = await use_case.execute(
            ConfirmOrderCommand(order_id=order.id, changed_by=uuid.uuid4())
        )

        assert result.status == "confirmed"
        assert result.lines[0].unit_price == Decimal("950.00")
        assert result.total_amount == Decimal("1900.00")
        cap_policy.evaluate.assert_called_once()
        credit_evaluator.evaluate.assert_called_once()
        mock_uow.commit.assert_called_once()

    async def test_missing_price_raises_and_saves_nothing(
        self, mock_order_repo: MagicMock, mock_uow: MagicMock
    ) -> None:
        order = _make_order()
        order.submit(changed_by=uuid.uuid4())
        mock_order_repo.get_by_id.return_value = order

        customer_repo = MagicMock()
        customer_repo.get_by_id = AsyncMock(
            return_value=_make_customer(customer_id=order.customer_id)
        )
        price_list_repo = MagicMock()
        price_list_repo.list_for_tenant_and_cylinder_type = AsyncMock(return_value=[])
        cap_policy = MagicMock()
        cap_policy.evaluate = AsyncMock()
        credit_evaluator = MagicMock()
        credit_evaluator.evaluate = AsyncMock()

        use_case = ConfirmOrderUseCase(
            mock_order_repo, customer_repo, price_list_repo, cap_policy, credit_evaluator, mock_uow
        )
        with pytest.raises(NotFoundError):
            await use_case.execute(ConfirmOrderCommand(order_id=order.id, changed_by=uuid.uuid4()))

        mock_order_repo.save.assert_not_called()
        mock_uow.commit.assert_not_called()


class TestDeliverOrderUseCase:
    def _deps(
        self,
        mock_order_repo: MagicMock,
        mock_route_repo: MagicMock,
        mock_inventory_repo: MagicMock,
        mock_uow: MagicMock,
    ) -> tuple[DeliverOrderUseCase, MagicMock, MagicMock]:
        pod_repo = MagicMock()
        pod_repo.next_id = MagicMock(return_value=uuid.uuid4())
        pod_repo.create = AsyncMock(
            return_value=ProofOfDeliveryEntry(
                id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                order_id=uuid.uuid4(),
                otp_verified_at=datetime.now(UTC),
                signature_blob_ref="sig",
                photo_blob_ref="photo",
                gps_lat=Decimal("12.9"),
                gps_lng=Decimal("77.6"),
                payment_method="cash",
                amount_collected=Decimal("100"),
                recorded_by=uuid.uuid4(),
                recorded_at=datetime.now(UTC),
            )
        )
        otp_store = MagicMock()
        otp_store.verify = AsyncMock(return_value=True)
        use_case = DeliverOrderUseCase(
            mock_order_repo, mock_route_repo, mock_inventory_repo, pod_repo, otp_store, mock_uow
        )
        return use_case, pod_repo, otp_store

    def _departed_order_and_route(
        self, cylinder_type_id: uuid.UUID, reserved: int = 4
    ) -> tuple[Order, Route]:
        order, route = _assigned_order_with_route(cylinder_type_id, reserved=reserved)
        order.dispatch(changed_by=uuid.uuid4())
        order.depart(changed_by=uuid.uuid4())
        route.change_status("loaded")
        route.change_status("in_progress")
        return order, route

    async def test_full_delivery_saves_all_and_commits_once(
        self,
        mock_order_repo: MagicMock,
        mock_route_repo: MagicMock,
        mock_inventory_repo: MagicMock,
        mock_uow: MagicMock,
    ) -> None:
        cylinder_type_id = uuid.uuid4()
        order, route = self._departed_order_and_route(cylinder_type_id, reserved=4)
        mock_order_repo.get_by_id.return_value = order
        _stub_route_lookup(mock_route_repo, route)
        vehicle_location = _make_vehicle_location(location_ref_id=route.vehicle_id)
        mock_inventory_repo.get_by_location_ref.return_value = vehicle_location
        use_case, pod_repo, _otp = self._deps(
            mock_order_repo, mock_route_repo, mock_inventory_repo, mock_uow
        )

        result = await use_case.execute(
            DeliverOrderCommand(
                order_id=order.id,
                lines=[DeliveredLine(cylinder_type_id=cylinder_type_id, quantity_delivered=4)],
                otp_code="123456",
                signature_blob_ref="sig-ref",
                photo_blob_ref="photo-ref",
                gps_lat=Decimal("12.9"),
                gps_lng=Decimal("77.6"),
                payment_method="cash",
                amount_collected=Decimal("3600"),
                changed_by=uuid.uuid4(),
            )
        )

        assert result.order.status == "delivered"
        assert route.stops[0].status == "delivered"
        mock_order_repo.save.assert_called_once()
        mock_inventory_repo.save.assert_called_once()
        mock_route_repo.save.assert_called_once()
        pod_repo.create.assert_called_once()
        mock_uow.commit.assert_called_once()

    async def test_wrong_otp_saves_nothing(
        self,
        mock_order_repo: MagicMock,
        mock_route_repo: MagicMock,
        mock_inventory_repo: MagicMock,
        mock_uow: MagicMock,
    ) -> None:
        cylinder_type_id = uuid.uuid4()
        order, route = self._departed_order_and_route(cylinder_type_id)
        mock_order_repo.get_by_id.return_value = order
        _stub_route_lookup(mock_route_repo, route)
        use_case, pod_repo, otp_store = self._deps(
            mock_order_repo, mock_route_repo, mock_inventory_repo, mock_uow
        )
        otp_store.verify = AsyncMock(return_value=False)

        with pytest.raises(OtpMismatchError):
            await use_case.execute(
                DeliverOrderCommand(
                    order_id=order.id,
                    lines=[DeliveredLine(cylinder_type_id=cylinder_type_id, quantity_delivered=4)],
                    otp_code="000000",
                    signature_blob_ref="sig-ref",
                    photo_blob_ref="photo-ref",
                    gps_lat=Decimal("12.9"),
                    gps_lng=Decimal("77.6"),
                    payment_method="cash",
                    amount_collected=Decimal("3600"),
                    changed_by=uuid.uuid4(),
                )
            )
        mock_order_repo.save.assert_not_called()
        mock_inventory_repo.save.assert_not_called()
        mock_route_repo.save.assert_not_called()
        pod_repo.create.assert_not_called()
        mock_uow.commit.assert_not_called()

    async def test_blank_signature_ref_saves_nothing(
        self,
        mock_order_repo: MagicMock,
        mock_route_repo: MagicMock,
        mock_inventory_repo: MagicMock,
        mock_uow: MagicMock,
    ) -> None:
        cylinder_type_id = uuid.uuid4()
        order, route = self._departed_order_and_route(cylinder_type_id)
        mock_order_repo.get_by_id.return_value = order
        _stub_route_lookup(mock_route_repo, route)
        use_case, pod_repo, _otp = self._deps(
            mock_order_repo, mock_route_repo, mock_inventory_repo, mock_uow
        )

        with pytest.raises(IncompletePodError):
            await use_case.execute(
                DeliverOrderCommand(
                    order_id=order.id,
                    lines=[DeliveredLine(cylinder_type_id=cylinder_type_id, quantity_delivered=4)],
                    otp_code="123456",
                    signature_blob_ref="   ",
                    photo_blob_ref="photo-ref",
                    gps_lat=Decimal("12.9"),
                    gps_lng=Decimal("77.6"),
                    payment_method="cash",
                    amount_collected=Decimal("3600"),
                    changed_by=uuid.uuid4(),
                )
            )
        mock_order_repo.save.assert_not_called()
        mock_route_repo.save.assert_not_called()
        pod_repo.create.assert_not_called()
        mock_uow.commit.assert_not_called()

    async def test_over_delivery_saves_nothing(
        self,
        mock_order_repo: MagicMock,
        mock_route_repo: MagicMock,
        mock_inventory_repo: MagicMock,
        mock_uow: MagicMock,
    ) -> None:
        cylinder_type_id = uuid.uuid4()
        order, route = self._departed_order_and_route(cylinder_type_id, reserved=4)
        mock_order_repo.get_by_id.return_value = order
        _stub_route_lookup(mock_route_repo, route)
        vehicle_location = _make_vehicle_location(location_ref_id=route.vehicle_id)
        mock_inventory_repo.get_by_location_ref.return_value = vehicle_location
        use_case, pod_repo, _otp = self._deps(
            mock_order_repo, mock_route_repo, mock_inventory_repo, mock_uow
        )

        with pytest.raises(InsufficientVehicleStockError):
            await use_case.execute(
                DeliverOrderCommand(
                    order_id=order.id,
                    lines=[DeliveredLine(cylinder_type_id=cylinder_type_id, quantity_delivered=99)],
                    otp_code="123456",
                    signature_blob_ref="sig-ref",
                    photo_blob_ref="photo-ref",
                    gps_lat=Decimal("12.9"),
                    gps_lng=Decimal("77.6"),
                    payment_method="cash",
                    amount_collected=Decimal("3600"),
                    changed_by=uuid.uuid4(),
                )
            )
        mock_order_repo.save.assert_not_called()
        mock_inventory_repo.save.assert_not_called()
        mock_route_repo.save.assert_not_called()
        pod_repo.create.assert_not_called()
        mock_uow.commit.assert_not_called()
        assert route.stops[0].status == "pending"


class TestCancelOrderUseCase:
    async def test_free_cancel_releases_reservation_and_cancels_route_stop(
        self,
        mock_order_repo: MagicMock,
        mock_route_repo: MagicMock,
        mock_inventory_repo: MagicMock,
        mock_uow: MagicMock,
    ) -> None:
        cylinder_type_id = uuid.uuid4()
        order, route = _assigned_order_with_route(cylinder_type_id, reserved=3)
        mock_order_repo.get_by_id.return_value = order
        _stub_route_lookup(mock_route_repo, route)

        vehicle_location = _make_vehicle_location(
            location_ref_id=route.vehicle_id, balances={(cylinder_type_id, "filled"): 7}
        )
        mock_inventory_repo.get_by_location_ref.return_value = vehicle_location

        cancellation_repo = MagicMock()
        use_case = CancelOrderUseCase(
            mock_order_repo, mock_route_repo, mock_inventory_repo, cancellation_repo, mock_uow
        )

        result = await use_case.execute(
            CancelOrderCommand(
                order_id=order.id, reason="Customer changed mind", cancelled_by=uuid.uuid4()
            )
        )

        assert result.pending_approval is False
        assert result.order.status == "cancelled"
        assert vehicle_location.balance_of(cylinder_type_id, "filled") == 10
        assert route.stops[0].status == "cancelled"
        mock_order_repo.save.assert_called_once()
        mock_inventory_repo.save.assert_called_once()
        mock_route_repo.save.assert_called_once()
        mock_uow.commit.assert_called_once()

    async def test_post_dispatch_cancel_creates_pending_record_without_status_change(
        self,
        mock_order_repo: MagicMock,
        mock_route_repo: MagicMock,
        mock_inventory_repo: MagicMock,
        mock_uow: MagicMock,
    ) -> None:
        cylinder_type_id = uuid.uuid4()
        order, _route = _assigned_order_with_route(cylinder_type_id, reserved=2)
        order.dispatch(changed_by=uuid.uuid4())
        order.depart(changed_by=uuid.uuid4())
        mock_order_repo.get_by_id.return_value = order

        cancellation_repo = MagicMock()
        cancellation_repo.next_id = MagicMock(return_value=uuid.uuid4())
        cancellation_repo.create = AsyncMock(
            return_value=CancellationRecordEntry(
                id=uuid.uuid4(),
                tenant_id=order.tenant_id,
                order_id=order.id,
                cancelled_by=uuid.uuid4(),
                approved_by=None,
                cancellation_charge=None,
                reason="Post-dispatch",
                requested_at=datetime.now(UTC),
                approved_at=None,
            )
        )
        use_case = CancelOrderUseCase(
            mock_order_repo, mock_route_repo, mock_inventory_repo, cancellation_repo, mock_uow
        )

        result = await use_case.execute(
            CancelOrderCommand(order_id=order.id, reason="Post-dispatch", cancelled_by=uuid.uuid4())
        )

        assert result.pending_approval is True
        assert result.order.status == "out_for_delivery"
        cancellation_repo.create.assert_called_once()
        mock_order_repo.save.assert_not_called()
        mock_route_repo.save.assert_not_called()
        mock_uow.commit.assert_called_once()

    async def test_missing_order_raises_not_found(
        self,
        mock_order_repo: MagicMock,
        mock_route_repo: MagicMock,
        mock_inventory_repo: MagicMock,
        mock_uow: MagicMock,
    ) -> None:
        cancellation_repo = MagicMock()
        use_case = CancelOrderUseCase(
            mock_order_repo, mock_route_repo, mock_inventory_repo, cancellation_repo, mock_uow
        )
        with pytest.raises(NotFoundError):
            await use_case.execute(
                CancelOrderCommand(order_id=uuid.uuid4(), reason="n/a", cancelled_by=uuid.uuid4())
            )
        mock_order_repo.save.assert_not_called()
        mock_uow.commit.assert_not_called()


class TestRescheduleOrderUseCase:
    """Regression coverage for the D-12 retry gap: `RescheduleOrderUseCase`
    used to leave the paired `RouteStop` stuck `failed` forever, which made
    the retry's later `deliver()` call 409 out of `Route.
    record_proof_of_delivery()`'s own transition guard.
    """

    def _failed_delivery_order_and_route(
        self, cylinder_type_id: uuid.UUID, reserved: int = 2
    ) -> tuple[Order, Route]:
        order, route = _assigned_order_with_route(cylinder_type_id, reserved=reserved)
        order.dispatch(changed_by=uuid.uuid4())
        order.depart(changed_by=uuid.uuid4())
        route.change_status("loaded")
        route.change_status("in_progress")
        stop_id = route.stops[0].id
        order.fail_delivery(
            reason_code="customer_unavailable",
            resolution_action="reschedule",
            recorded_by=uuid.uuid4(),
        )
        route.record_failed_delivery(stop_id, "customer_unavailable")
        return order, route

    async def test_resets_route_stop_and_saves_both_aggregates(
        self,
        mock_order_repo: MagicMock,
        mock_route_repo: MagicMock,
        mock_uow: MagicMock,
    ) -> None:
        cylinder_type_id = uuid.uuid4()
        order, route = self._failed_delivery_order_and_route(cylinder_type_id)
        mock_order_repo.get_by_id.return_value = order
        _stub_route_lookup(mock_route_repo, route)

        use_case = RescheduleOrderUseCase(mock_order_repo, mock_route_repo, mock_uow)
        result = await use_case.execute(
            RescheduleOrderCommand(order_id=order.id, changed_by=uuid.uuid4())
        )

        assert result.status == "ready_for_dispatch"
        assert route.stops[0].status == "pending"
        mock_order_repo.save.assert_called_once()
        mock_route_repo.save.assert_called_once()
        mock_uow.commit.assert_called_once()

    async def test_missing_order_raises_not_found(
        self, mock_order_repo: MagicMock, mock_route_repo: MagicMock, mock_uow: MagicMock
    ) -> None:
        use_case = RescheduleOrderUseCase(mock_order_repo, mock_route_repo, mock_uow)
        with pytest.raises(NotFoundError):
            await use_case.execute(
                RescheduleOrderCommand(order_id=uuid.uuid4(), changed_by=uuid.uuid4())
            )
        mock_order_repo.save.assert_not_called()
        mock_uow.commit.assert_not_called()


def _single_use_case_factory(
    cancel_use_case: MagicMock,
) -> Callable[[], AbstractAsyncContextManager[MagicMock]]:
    """`BulkCancelOrdersUseCase` requires a *fresh*-`CancelOrderUseCase`
    factory in production (see its own docstring) — for these mocked-repo
    tests, returning the one shared mock via a trivial async context
    manager is enough to exercise the loop/error-isolation logic.
    """

    @asynccontextmanager
    async def _factory() -> AsyncIterator[MagicMock]:
        yield cancel_use_case

    return _factory


class TestBulkCancelOrdersUseCase:
    async def test_over_threshold_enqueues_a_job(self) -> None:
        cancel_use_case = MagicMock()
        job_queue = MagicMock()
        job_queue.enqueue = AsyncMock(return_value="job-123")
        use_case = BulkCancelOrdersUseCase(_single_use_case_factory(cancel_use_case), job_queue)

        order_ids = [uuid.uuid4() for _ in range(51)]
        result = await use_case.execute(
            BulkCancelOrdersCommand(
                tenant_id=uuid.uuid4(),
                order_ids=order_ids,
                reason="Bulk",
                cancelled_by=uuid.uuid4(),
            )
        )

        assert result.job_id == "job-123"
        assert result.results is None
        job_queue.enqueue.assert_called_once()

    async def test_under_threshold_runs_synchronously_and_isolates_failures(self) -> None:
        cancel_use_case = MagicMock()
        good_id, bad_id = uuid.uuid4(), uuid.uuid4()

        async def _execute(command: CancelOrderCommand) -> MagicMock:
            if command.order_id == bad_id:
                raise NotFoundError("no such order", order_id=str(bad_id))
            return MagicMock()

        cancel_use_case.execute = AsyncMock(side_effect=_execute)
        job_queue = MagicMock()
        use_case = BulkCancelOrdersUseCase(_single_use_case_factory(cancel_use_case), job_queue)

        result = await use_case.execute(
            BulkCancelOrdersCommand(
                tenant_id=uuid.uuid4(),
                order_ids=[good_id, bad_id],
                reason="Bulk",
                cancelled_by=uuid.uuid4(),
            )
        )

        assert result.job_id is None
        assert result.results is not None
        by_id = {r.order_id: r for r in result.results}
        assert by_id[good_id].succeeded is True
        assert by_id[bad_id].succeeded is False
        assert by_id[bad_id].error_code == "RESOURCE_NOT_FOUND"
        job_queue.enqueue.assert_not_called()

    async def test_under_threshold_opens_a_fresh_use_case_per_order(self) -> None:
        """Regression test: a single shared `UnitOfWork`/`CancelOrderUseCase`
        reused across the loop silently broke every order after the first
        (RLS's tenant GUC resets on the first commit; `UnitOfWork.commit()`
        is a one-shot no-op after that). The factory must be invoked once
        per order, each call yielding its own use case.
        """
        order_ids = [uuid.uuid4() for _ in range(3)]
        opened: list[MagicMock] = []

        @asynccontextmanager
        async def factory() -> AsyncIterator[MagicMock]:
            use_case = MagicMock()
            use_case.execute = AsyncMock(return_value=MagicMock())
            opened.append(use_case)
            yield use_case

        job_queue = MagicMock()
        use_case = BulkCancelOrdersUseCase(factory, job_queue)

        result = await use_case.execute(
            BulkCancelOrdersCommand(
                tenant_id=uuid.uuid4(),
                order_ids=order_ids,
                reason="Bulk",
                cancelled_by=uuid.uuid4(),
            )
        )

        assert len(opened) == len(order_ids)
        assert result.results is not None
        assert all(r.succeeded for r in result.results)
        for opened_use_case in opened:
            opened_use_case.execute.assert_awaited_once()
