"""Unit tests for the Order aggregate root.

Validates every `_TRANSITIONS` edge (valid and the illegal ones the D-19
free/approval split additionally guards against), BR-08's over-delivery
guard, D-08's backorder allocation, and event/pending-record payload shapes
— all without touching the database.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from lpg.domain.common.base import InvariantViolation
from lpg.domain.order.order import (
    BookingCancelled,
    BookingCreated,
    DeliveredLine,
    DeliveryAddress,
    InsufficientVehicleStockError,
    InvalidOrderStatusTransitionError,
    InventoryReserved,
    Order,
    OrderClosed,
    OrderLine,
)


def _make_line(quantity_ordered: int = 2, cylinder_type_id: uuid.UUID | None = None) -> OrderLine:
    return OrderLine(
        line_id=uuid.uuid4(),
        cylinder_type_id=cylinder_type_id or uuid.uuid4(),
        quantity_ordered=quantity_ordered,
    )


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
        "lines": [_make_line()],
    }
    defaults.update(kwargs)
    return Order(**defaults)  # type: ignore[arg-type]


def _confirm(order: Order, unit_price: Decimal = Decimal("900")) -> None:
    prices = {line.cylinder_type_id: unit_price for line in order.lines}
    order.confirm(unit_prices=prices, changed_by=uuid.uuid4())


def _assign(order: Order, *, reserved: int | None = None) -> None:
    line = order.lines[0]
    qty = reserved if reserved is not None else line.quantity_ordered
    order.assign(
        route_stop_id=uuid.uuid4(),
        reservations={line.cylinder_type_id: qty},
        backorders={line.cylinder_type_id: line.quantity_ordered - qty},
        changed_by=uuid.uuid4(),
    )


def _advance(order: Order, target_status: str) -> None:
    """Walk the order forward through the happy path up to `target_status`."""
    sequence = [
        "draft",
        "booked",
        "confirmed",
        "assigned",
        "ready_for_dispatch",
        "out_for_delivery",
    ]
    idx = sequence.index(target_status)
    if idx >= 1:
        order.submit(changed_by=uuid.uuid4())
    if idx >= 2:
        _confirm(order)
    if idx >= 3:
        _assign(order)
    if idx >= 4:
        order.dispatch(changed_by=uuid.uuid4())
    if idx >= 5:
        order.depart(changed_by=uuid.uuid4())


class TestOrderConstruction:
    def test_creates_in_draft_status(self) -> None:
        order = _make_order()
        assert order.status == "draft"
        assert len(order.lines) == 1
        assert order.pending_status_history == ()

    def test_rejects_unknown_booking_source(self) -> None:
        with pytest.raises(InvariantViolation, match="booking source"):
            _make_order(booking_source="carrier_pigeon")

    def test_rejects_empty_lines(self) -> None:
        with pytest.raises(InvariantViolation, match="at least one line"):
            _make_order(lines=[])

    def test_rejects_invalid_payment_method(self) -> None:
        with pytest.raises(InvariantViolation, match="payment method"):
            _make_order(payment_method_preference="bitcoin")

    def test_rejects_unknown_status(self) -> None:
        with pytest.raises(InvariantViolation, match="status"):
            _make_order(status="shipped")


class TestOrderTransitions:
    """Every valid edge in `_TRANSITIONS`, plus a representative sample of
    illegal ones — including edges the underlying transition graph would
    technically allow but the free/approval-cancel split forbids.
    """

    @pytest.mark.parametrize(
        "target_status",
        ["booked", "confirmed", "assigned", "ready_for_dispatch", "out_for_delivery"],
    )
    def test_valid_forward_transition(self, target_status: str) -> None:
        order = _make_order()
        _advance(order, target_status)
        assert order.status == target_status

    def test_out_for_delivery_to_delivered(self) -> None:
        order = _make_order()
        _advance(order, "out_for_delivery")
        line = order.lines[0]
        order.deliver(
            lines=[DeliveredLine(cylinder_type_id=line.cylinder_type_id, quantity_delivered=2)],
            changed_by=uuid.uuid4(),
        )
        assert order.status == "delivered"

    def test_out_for_delivery_to_failed_delivery(self) -> None:
        order = _make_order()
        _advance(order, "out_for_delivery")
        order.fail_delivery(
            reason_code="customer_unavailable",
            resolution_action="reschedule",
            recorded_by=uuid.uuid4(),
        )
        assert order.status == "failed_delivery"

    def test_failed_delivery_to_ready_for_dispatch(self) -> None:
        order = _make_order()
        _advance(order, "out_for_delivery")
        order.fail_delivery(
            reason_code="wrong_address", resolution_action="reschedule", recorded_by=uuid.uuid4()
        )
        order.reschedule(changed_by=uuid.uuid4())
        assert order.status == "ready_for_dispatch"

    def test_delivered_to_closed(self) -> None:
        order = _make_order()
        _advance(order, "out_for_delivery")
        line = order.lines[0]
        order.deliver(
            lines=[DeliveredLine(cylinder_type_id=line.cylinder_type_id, quantity_delivered=2)],
            changed_by=uuid.uuid4(),
        )
        order.close(closed_by=uuid.uuid4())
        assert order.status == "closed"

    @pytest.mark.parametrize(
        ("start_status", "illegal_method"),
        [
            ("draft", "confirm_direct"),
            ("booked", "assign_direct"),
            ("confirmed", "dispatch_direct"),
        ],
    )
    def test_skipping_a_state_is_rejected(self, start_status: str, illegal_method: str) -> None:
        order = _make_order()
        _advance(order, start_status)
        with pytest.raises(InvalidOrderStatusTransitionError) as exc_info:
            if illegal_method == "confirm_direct":
                order.assign(
                    route_stop_id=uuid.uuid4(),
                    reservations={},
                    backorders={},
                    changed_by=uuid.uuid4(),
                )
            elif illegal_method == "assign_direct":
                order.dispatch(changed_by=uuid.uuid4())
            else:
                order.depart(changed_by=uuid.uuid4())
        assert exc_info.value.error_code == "INVALID_STATE_TRANSITION"

    def test_cancelled_is_terminal(self) -> None:
        order = _make_order()
        order.submit(changed_by=uuid.uuid4())
        order.cancel_free(cancelled_by=uuid.uuid4(), reason="Changed my mind")
        with pytest.raises(InvalidOrderStatusTransitionError):
            order.submit(changed_by=uuid.uuid4())

    def test_closed_is_terminal(self) -> None:
        order = _make_order()
        _advance(order, "out_for_delivery")
        line = order.lines[0]
        order.deliver(
            lines=[DeliveredLine(cylinder_type_id=line.cylinder_type_id, quantity_delivered=2)],
            changed_by=uuid.uuid4(),
        )
        order.close(closed_by=uuid.uuid4())
        with pytest.raises(InvalidOrderStatusTransitionError):
            order.close(closed_by=uuid.uuid4())

    def test_records_status_history(self) -> None:
        order = _make_order()
        order.submit(changed_by=uuid.uuid4())
        assert len(order.pending_status_history) == 1
        entry = order.pending_status_history[0]
        assert entry.from_status == "draft"
        assert entry.to_status == "booked"

    def test_records_booking_created_event(self) -> None:
        order = _make_order()
        order.submit(changed_by=uuid.uuid4())
        events = [e for e in order.events if isinstance(e, BookingCreated)]
        assert len(events) == 1
        assert events[0].booking_source == "staff"


class TestOrderConfirm:
    def test_snapshots_unit_price_and_computes_total(self) -> None:
        order = _make_order(lines=[_make_line(quantity_ordered=3)])
        order.submit(changed_by=uuid.uuid4())
        line = order.lines[0]

        order.confirm(
            unit_prices={line.cylinder_type_id: Decimal("950.00")}, changed_by=uuid.uuid4()
        )

        assert order.lines[0].unit_price == Decimal("950.00")
        assert order.total_amount == Decimal("2850.00")
        assert order.status == "confirmed"

    def test_rejects_missing_price_for_a_line(self) -> None:
        order = _make_order()
        order.submit(changed_by=uuid.uuid4())
        with pytest.raises(InvariantViolation, match="No price configured"):
            order.confirm(unit_prices={}, changed_by=uuid.uuid4())


class TestOrderAssign:
    def test_full_allocation_leaves_no_backorder(self) -> None:
        order = _make_order(lines=[_make_line(quantity_ordered=5)])
        order.submit(changed_by=uuid.uuid4())
        _confirm(order)
        line = order.lines[0]

        order.assign(
            route_stop_id=uuid.uuid4(),
            reservations={line.cylinder_type_id: 5},
            backorders={line.cylinder_type_id: 0},
            changed_by=uuid.uuid4(),
        )

        assert order.lines[0].is_backordered is False
        assert order.lines[0].quantity_pending == 0
        assert order.status == "assigned"

    def test_partial_allocation_sets_backorder(self) -> None:
        order = _make_order(lines=[_make_line(quantity_ordered=5)])
        order.submit(changed_by=uuid.uuid4())
        _confirm(order)
        line = order.lines[0]

        order.assign(
            route_stop_id=uuid.uuid4(),
            reservations={line.cylinder_type_id: 3},
            backorders={line.cylinder_type_id: 2},
            changed_by=uuid.uuid4(),
        )

        assert order.lines[0].is_backordered is True
        assert order.lines[0].quantity_pending == 2

    def test_records_inventory_reserved_event(self) -> None:
        order = _make_order()
        order.submit(changed_by=uuid.uuid4())
        _confirm(order)
        route_stop_id = uuid.uuid4()
        line = order.lines[0]

        order.assign(
            route_stop_id=route_stop_id,
            reservations={line.cylinder_type_id: line.quantity_ordered},
            backorders={line.cylinder_type_id: 0},
            changed_by=uuid.uuid4(),
        )

        events = [e for e in order.events if isinstance(e, InventoryReserved)]
        assert len(events) == 1
        assert events[0].route_stop_id == route_stop_id

    def test_sets_route_stop_id(self) -> None:
        order = _make_order()
        order.submit(changed_by=uuid.uuid4())
        _confirm(order)
        route_stop_id = uuid.uuid4()
        line = order.lines[0]

        order.assign(
            route_stop_id=route_stop_id,
            reservations={line.cylinder_type_id: line.quantity_ordered},
            backorders={line.cylinder_type_id: 0},
            changed_by=uuid.uuid4(),
        )

        assert order.route_stop_id == route_stop_id


class TestOrderDeliver:
    def test_full_delivery_sets_quantity_delivered(self) -> None:
        order = _make_order(lines=[_make_line(quantity_ordered=4)])
        _advance(order, "out_for_delivery")
        line = order.lines[0]

        order.deliver(
            lines=[
                DeliveredLine(
                    cylinder_type_id=line.cylinder_type_id,
                    quantity_delivered=4,
                    quantity_collected_empty=3,
                )
            ],
            changed_by=uuid.uuid4(),
        )

        assert order.lines[0].quantity_delivered == 4
        assert order.lines[0].quantity_collected_empty == 3
        assert order.status == "delivered"

    def test_over_delivery_beyond_reserved_is_rejected(self) -> None:
        order = _make_order(lines=[_make_line(quantity_ordered=5)])
        order.submit(changed_by=uuid.uuid4())
        _confirm(order)
        line = order.lines[0]
        # Only 3 reserved (2 backordered) at assignment.
        order.assign(
            route_stop_id=uuid.uuid4(),
            reservations={line.cylinder_type_id: 3},
            backorders={line.cylinder_type_id: 2},
            changed_by=uuid.uuid4(),
        )
        order.dispatch(changed_by=uuid.uuid4())
        order.depart(changed_by=uuid.uuid4())

        with pytest.raises(InsufficientVehicleStockError) as exc_info:
            order.deliver(
                lines=[DeliveredLine(cylinder_type_id=line.cylinder_type_id, quantity_delivered=4)],
                changed_by=uuid.uuid4(),
            )
        assert exc_info.value.error_code == "INSUFFICIENT_VEHICLE_STOCK"

    def test_delivering_an_unknown_cylinder_type_is_rejected(self) -> None:
        order = _make_order()
        _advance(order, "out_for_delivery")
        with pytest.raises(InvariantViolation, match="no line for cylinder type"):
            order.deliver(
                lines=[DeliveredLine(cylinder_type_id=uuid.uuid4(), quantity_delivered=1)],
                changed_by=uuid.uuid4(),
            )


class TestOrderFailDelivery:
    def test_rejects_invalid_reason_code(self) -> None:
        order = _make_order()
        _advance(order, "out_for_delivery")
        with pytest.raises(InvariantViolation, match="reason code"):
            order.fail_delivery(
                reason_code="dog_ate_it", resolution_action=None, recorded_by=uuid.uuid4()
            )

    def test_rejects_invalid_resolution_action(self) -> None:
        order = _make_order()
        _advance(order, "out_for_delivery")
        with pytest.raises(InvariantViolation, match="resolution action"):
            order.fail_delivery(
                reason_code="vehicle_issue", resolution_action="teleport", recorded_by=uuid.uuid4()
            )

    def test_appends_pending_failed_delivery_entry(self) -> None:
        order = _make_order()
        _advance(order, "out_for_delivery")
        order.fail_delivery(
            reason_code="payment_refused", resolution_action="cancel", recorded_by=uuid.uuid4()
        )
        assert len(order.pending_failed_delivery_entries) == 1
        entry = order.pending_failed_delivery_entries[0]
        assert entry.reason_code == "payment_refused"
        assert entry.resolution_action == "cancel"


class TestOrderCancelFree:
    @pytest.mark.parametrize("status", ["booked", "confirmed", "assigned", "ready_for_dispatch"])
    def test_cancels_from_every_free_state(self, status: str) -> None:
        order = _make_order()
        _advance(order, status)
        order.cancel_free(cancelled_by=uuid.uuid4(), reason="No longer needed")
        assert order.status == "cancelled"

    @pytest.mark.parametrize("status", ["out_for_delivery", "draft"])
    def test_rejects_from_non_free_states(self, status: str) -> None:
        order = _make_order()
        _advance(order, status)
        with pytest.raises(InvalidOrderStatusTransitionError):
            order.cancel_free(cancelled_by=uuid.uuid4(), reason="No longer needed")

    def test_records_booking_cancelled_event_without_charge(self) -> None:
        order = _make_order()
        _advance(order, "booked")
        order.cancel_free(cancelled_by=uuid.uuid4(), reason="Duplicate booking")
        events = [e for e in order.events if isinstance(e, BookingCancelled)]
        assert len(events) == 1
        assert events[0].approved_by is None
        assert events[0].cancellation_charge is None


class TestOrderCancellationApproval:
    @pytest.mark.parametrize("status", ["out_for_delivery", "failed_delivery"])
    def test_request_approval_allowed_only_from_approval_states(self, status: str) -> None:
        order = _make_order()
        _advance(order, "out_for_delivery")
        if status == "failed_delivery":
            order.fail_delivery(
                reason_code="vehicle_issue", resolution_action=None, recorded_by=uuid.uuid4()
            )
        order.request_cancellation_approval(reason="Customer changed mind post-dispatch")
        # Status is unchanged — the use case, not the aggregate, records the
        # pending CancellationRecord.
        assert order.status == status

    def test_request_approval_rejects_free_states(self) -> None:
        order = _make_order()
        _advance(order, "booked")
        with pytest.raises(InvariantViolation, match="does not require Manager approval"):
            order.request_cancellation_approval(reason="Too early for approval")

    def test_request_approval_rejects_empty_reason(self) -> None:
        order = _make_order()
        _advance(order, "out_for_delivery")
        with pytest.raises(InvariantViolation, match="cannot be empty"):
            order.request_cancellation_approval(reason="   ")

    def test_approve_cancellation_transitions_and_records_charge(self) -> None:
        order = _make_order()
        _advance(order, "out_for_delivery")
        order.request_cancellation_approval(reason="Post-dispatch cancellation")

        order.approve_cancellation(
            approved_by=uuid.uuid4(),
            cancellation_charge=Decimal("150.00"),
            reason="Approved by manager",
        )

        assert order.status == "cancelled"
        events = [e for e in order.events if isinstance(e, BookingCancelled)]
        assert events[-1].cancellation_charge == Decimal("150.00")
        assert events[-1].approved_by is not None

    def test_approve_cancellation_rejects_free_states(self) -> None:
        order = _make_order()
        _advance(order, "booked")
        with pytest.raises(InvalidOrderStatusTransitionError):
            order.approve_cancellation(
                approved_by=uuid.uuid4(), cancellation_charge=Decimal("0"), reason="n/a"
            )

    def test_approve_cancellation_rejects_negative_charge(self) -> None:
        order = _make_order()
        _advance(order, "out_for_delivery")
        with pytest.raises(InvariantViolation, match="cannot be negative"):
            order.approve_cancellation(
                approved_by=uuid.uuid4(), cancellation_charge=Decimal("-1"), reason="n/a"
            )


class TestOrderClose:
    def test_close_only_from_delivered(self) -> None:
        order = _make_order()
        _advance(order, "booked")
        with pytest.raises(InvalidOrderStatusTransitionError):
            order.close(closed_by=uuid.uuid4())

    def test_close_records_order_closed_event(self) -> None:
        order = _make_order()
        _advance(order, "out_for_delivery")
        line = order.lines[0]
        order.deliver(
            lines=[DeliveredLine(cylinder_type_id=line.cylinder_type_id, quantity_delivered=2)],
            changed_by=uuid.uuid4(),
        )
        closer = uuid.uuid4()
        order.close(closed_by=closer)
        events = [e for e in order.events if isinstance(e, OrderClosed)]
        assert len(events) == 1
        assert events[0].closed_by == closer
