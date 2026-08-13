"""Unit tests for the InventoryLocation aggregate root.

Validates the never-negative invariant, every `_STATUS_TRANSITIONS` edge
(including the two deliberately-absent filled<->empty pairs), warehouse/
vehicle-only guards, and event/transaction-record payload shapes — all
without touching the database.
"""

from __future__ import annotations

import uuid

import pytest

from lpg.domain.common.base import InvariantViolation
from lpg.domain.inventory.inventory_location import (
    GoodsReceived,
    InsufficientStockError,
    InvalidStatusTransitionError,
    InventoryAdjusted,
    InventoryLocation,
)


def _make_location(location_type: str = "warehouse", **kwargs: object) -> InventoryLocation:
    defaults: dict[str, object] = {
        "inventory_location_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "location_type": location_type,
        "location_ref_id": uuid.uuid4(),
    }
    defaults.update(kwargs)
    return InventoryLocation(**defaults)  # type: ignore[arg-type]


def _location_with_balance(
    cylinder_type_id: uuid.UUID, status: str, quantity: int, **kwargs: object
) -> InventoryLocation:
    """A location pre-seeded with balance directly via the constructor — the
    only way to fund a status like "empty" that no public mutation method
    credits directly on a warehouse (`receive_goods` always credits
    "filled"; `record_collection` is vehicle-only).
    """
    return _make_location(balances={(cylinder_type_id, status): quantity}, **kwargs)


class TestInventoryLocationCreation:
    def test_creates_with_valid_data(self) -> None:
        location = _make_location(location_type="vehicle")
        assert location.location_type == "vehicle"
        assert location.balances == {}
        assert location.pending_transactions == ()

    def test_raises_on_invalid_location_type(self) -> None:
        with pytest.raises(InvariantViolation, match="location type"):
            _make_location(location_type="depot")


class TestReceiveGoods:
    def test_credits_filled_balance(self) -> None:
        location = _make_location()
        cylinder_type_id = uuid.uuid4()
        performer = uuid.uuid4()

        location.receive_goods(cylinder_type_id, 50, performed_by=performer)

        assert location.balance_of(cylinder_type_id, "filled") == 50
        assert len(location.pending_transactions) == 1
        txn = location.pending_transactions[0]
        assert txn.transaction_type == "grn_receipt"
        assert txn.from_status is None
        assert txn.to_status == "filled"
        assert txn.quantity == 50

    def test_records_goods_received_event(self) -> None:
        location = _make_location()
        cylinder_type_id = uuid.uuid4()
        location.receive_goods(cylinder_type_id, 10, performed_by=uuid.uuid4())
        events = [e for e in location.events if isinstance(e, GoodsReceived)]
        assert len(events) == 1
        assert events[0].quantity == 10

    def test_rejects_vehicle_location(self) -> None:
        location = _make_location(location_type="vehicle")
        with pytest.raises(InvariantViolation, match="warehouse"):
            location.receive_goods(uuid.uuid4(), 10, performed_by=uuid.uuid4())

    def test_rejects_zero_quantity(self) -> None:
        location = _make_location()
        with pytest.raises(InvariantViolation, match="Quantity"):
            location.receive_goods(uuid.uuid4(), 0, performed_by=uuid.uuid4())


class TestLoadUnload:
    def test_unload_debits_warehouse(self) -> None:
        location = _make_location()
        cylinder_type_id = uuid.uuid4()
        location.receive_goods(cylinder_type_id, 50, performed_by=uuid.uuid4())
        location.unload(cylinder_type_id, "filled", 20, performed_by=uuid.uuid4())
        assert location.balance_of(cylinder_type_id, "filled") == 30

    def test_unload_rejects_vehicle_location(self) -> None:
        location = _make_location(location_type="vehicle")
        with pytest.raises(InvariantViolation, match="warehouse"):
            location.unload(uuid.uuid4(), "filled", 5, performed_by=uuid.uuid4())

    def test_load_credits_vehicle(self) -> None:
        location = _make_location(location_type="vehicle")
        cylinder_type_id = uuid.uuid4()
        location.load(cylinder_type_id, "filled", 15, performed_by=uuid.uuid4())
        assert location.balance_of(cylinder_type_id, "filled") == 15

    def test_load_rejects_warehouse_location(self) -> None:
        location = _make_location(location_type="warehouse")
        with pytest.raises(InvariantViolation, match="vehicle"):
            location.load(uuid.uuid4(), "filled", 5, performed_by=uuid.uuid4())

    def test_unload_raises_insufficient_stock(self) -> None:
        location = _make_location()
        cylinder_type_id = uuid.uuid4()
        location.receive_goods(cylinder_type_id, 10, performed_by=uuid.uuid4())
        with pytest.raises(InsufficientStockError) as exc_info:
            location.unload(cylinder_type_id, "filled", 11, performed_by=uuid.uuid4())
        assert exc_info.value.error_code == "INSUFFICIENT_STOCK"

    def test_debit_never_goes_negative_on_empty_balance(self) -> None:
        location = _make_location()
        with pytest.raises(InsufficientStockError):
            location.unload(uuid.uuid4(), "filled", 1, performed_by=uuid.uuid4())


class TestDeliveryAndCollection:
    def test_delivery_and_collection_move_independently(self) -> None:
        """BR-13's worked example: Filled 50->35 delivering 15, Empty
        10->24 collecting 14 — not a 1:1, same-status transition.
        """
        location = _make_location(location_type="vehicle")
        cylinder_type_id = uuid.uuid4()
        performer = uuid.uuid4()
        location.load(cylinder_type_id, "filled", 50, performed_by=performer)
        location.load(cylinder_type_id, "empty", 10, performed_by=performer)

        location.record_delivery(cylinder_type_id, 15, performed_by=performer)
        location.record_collection(cylinder_type_id, 14, performed_by=performer)

        assert location.balance_of(cylinder_type_id, "filled") == 35
        assert location.balance_of(cylinder_type_id, "empty") == 24

    def test_record_delivery_rejects_warehouse(self) -> None:
        location = _make_location(location_type="warehouse")
        with pytest.raises(InvariantViolation, match="vehicle"):
            location.record_delivery(uuid.uuid4(), 1, performed_by=uuid.uuid4())

    def test_record_collection_rejects_warehouse(self) -> None:
        location = _make_location(location_type="warehouse")
        with pytest.raises(InvariantViolation, match="vehicle"):
            location.record_collection(uuid.uuid4(), 1, performed_by=uuid.uuid4())


class TestReserveAndReleaseReservation:
    """Order Management's assign/cancel use the same debit/credit-Filled
    shape as record_delivery/record_collection but a distinct
    transaction_type, so a reservation is never confused with an actual
    delivery when reading the transaction ledger.
    """

    def test_reserve_debits_filled(self) -> None:
        location = _make_location(location_type="vehicle")
        cylinder_type_id = uuid.uuid4()
        performer = uuid.uuid4()
        location.load(cylinder_type_id, "filled", 20, performed_by=performer)

        location.reserve(cylinder_type_id, 8, performed_by=performer)

        assert location.balance_of(cylinder_type_id, "filled") == 12
        txn = location.pending_transactions[-1]
        assert txn.transaction_type == "reservation"
        assert txn.from_status == "filled"
        assert txn.to_status == "filled"
        assert txn.quantity == 8

    def test_reserve_rejects_insufficient_stock(self) -> None:
        location = _make_location(location_type="vehicle")
        cylinder_type_id = uuid.uuid4()
        location.load(cylinder_type_id, "filled", 5, performed_by=uuid.uuid4())
        with pytest.raises(InsufficientStockError):
            location.reserve(cylinder_type_id, 6, performed_by=uuid.uuid4())

    def test_reserve_rejects_warehouse(self) -> None:
        location = _make_location(location_type="warehouse")
        with pytest.raises(InvariantViolation, match="vehicle"):
            location.reserve(uuid.uuid4(), 1, performed_by=uuid.uuid4())

    def test_release_reservation_credits_filled_back(self) -> None:
        location = _make_location(location_type="vehicle")
        cylinder_type_id = uuid.uuid4()
        performer = uuid.uuid4()
        location.load(cylinder_type_id, "filled", 20, performed_by=performer)
        location.reserve(cylinder_type_id, 8, performed_by=performer)

        location.release_reservation(cylinder_type_id, 8, performed_by=performer)

        assert location.balance_of(cylinder_type_id, "filled") == 20
        txn = location.pending_transactions[-1]
        assert txn.transaction_type == "reservation_release"
        assert txn.quantity == 8

    def test_release_reservation_rejects_warehouse(self) -> None:
        location = _make_location(location_type="warehouse")
        with pytest.raises(InvariantViolation, match="vehicle"):
            location.release_reservation(uuid.uuid4(), 1, performed_by=uuid.uuid4())

    def test_reserve_records_reference_order_id(self) -> None:
        location = _make_location(location_type="vehicle")
        cylinder_type_id = uuid.uuid4()
        order_id = uuid.uuid4()
        location.load(cylinder_type_id, "filled", 20, performed_by=uuid.uuid4())

        location.reserve(
            cylinder_type_id, 5, performed_by=uuid.uuid4(), reference_order_id=order_id
        )

        assert location.pending_transactions[-1].reference_order_id == order_id


def _move(
    location: InventoryLocation,
    cylinder_type_id: uuid.UUID,
    from_status: str,
    to_status: str,
    quantity: int = 10,
) -> None:
    location.change_status(
        cylinder_type_id, from_status, to_status, quantity, performed_by=uuid.uuid4()
    )


class TestStatusTransitions:
    """Every edge in `_STATUS_TRANSITIONS`, plus the two deliberately-absent
    filled<->empty pairs.
    """

    @pytest.mark.parametrize(
        ("from_status", "to_status"),
        [
            ("empty", "damaged"),
            ("empty", "leakage"),
            ("filled", "leakage"),
            ("damaged", "quarantine"),
            ("leakage", "quarantine"),
            ("quarantine", "repair"),
            ("quarantine", "scrap"),
            ("repair", "filled"),
        ],
    )
    def test_valid_transition(self, from_status: str, to_status: str) -> None:
        cylinder_type_id = uuid.uuid4()
        location = _location_with_balance(cylinder_type_id, from_status, 10)
        _move(location, cylinder_type_id, from_status, to_status)
        assert location.balance_of(cylinder_type_id, to_status) == 10

    def test_filled_to_empty_rejected(self) -> None:
        location = _make_location()
        cylinder_type_id = uuid.uuid4()
        location.receive_goods(cylinder_type_id, 10, performed_by=uuid.uuid4())
        with pytest.raises(InvalidStatusTransitionError) as exc_info:
            _move(location, cylinder_type_id, "filled", "empty", 5)
        assert exc_info.value.error_code == "INVALID_STATUS_TRANSITION"

    def test_empty_to_filled_rejected(self) -> None:
        location = _make_location()
        cylinder_type_id = uuid.uuid4()
        with pytest.raises(InvalidStatusTransitionError):
            _move(location, cylinder_type_id, "empty", "filled", 1)

    def test_scrap_is_terminal(self) -> None:
        cylinder_type_id = uuid.uuid4()
        location = _location_with_balance(cylinder_type_id, "empty", 5)
        _move(location, cylinder_type_id, "empty", "damaged", 5)
        _move(location, cylinder_type_id, "damaged", "quarantine", 5)
        _move(location, cylinder_type_id, "quarantine", "scrap", 5)
        with pytest.raises(InvalidStatusTransitionError):
            _move(location, cylinder_type_id, "scrap", "filled", 5)

    def test_records_inventory_adjusted_event(self) -> None:
        cylinder_type_id = uuid.uuid4()
        location = _location_with_balance(cylinder_type_id, "empty", 5)
        _move(location, cylinder_type_id, "empty", "damaged", 5)
        events = [e for e in location.events if isinstance(e, InventoryAdjusted)]
        assert len(events) == 1
        assert events[0].transaction_type == "status_change"
        assert events[0].from_status == "empty"
        assert events[0].to_status == "damaged"

    def test_change_status_debits_never_negative(self) -> None:
        location = _make_location()
        with pytest.raises(InsufficientStockError):
            location.change_status(uuid.uuid4(), "empty", "damaged", 1, performed_by=uuid.uuid4())


class TestAdjust:
    def test_adjust_moves_stock_with_reason(self) -> None:
        location = _make_location()
        cylinder_type_id = uuid.uuid4()
        location.receive_goods(cylinder_type_id, 10, performed_by=uuid.uuid4())
        location.change_status(cylinder_type_id, "filled", "leakage", 3, performed_by=uuid.uuid4())
        location.adjust(
            cylinder_type_id,
            "leakage",
            "quarantine",
            3,
            performed_by=uuid.uuid4(),
            reason="Inspection found leaking cylinders",
        )
        assert location.balance_of(cylinder_type_id, "quarantine") == 3
        txn = location.pending_transactions[-1]
        assert txn.transaction_type == "adjustment"
        assert txn.reason == "Inspection found leaking cylinders"

    def test_adjust_rejects_invalid_transition(self) -> None:
        location = _make_location()
        cylinder_type_id = uuid.uuid4()
        location.receive_goods(cylinder_type_id, 10, performed_by=uuid.uuid4())
        with pytest.raises(InvalidStatusTransitionError):
            location.adjust(
                cylinder_type_id, "filled", "empty", 1, performed_by=uuid.uuid4(), reason="oops"
            )


class TestReconcile:
    def test_reconcile_sets_balance_and_records_positive_variance(self) -> None:
        location = _make_location()
        cylinder_type_id = uuid.uuid4()
        location.receive_goods(cylinder_type_id, 50, performed_by=uuid.uuid4())

        location.reconcile(cylinder_type_id, "filled", 55, performed_by=uuid.uuid4())

        assert location.balance_of(cylinder_type_id, "filled") == 55
        txn = location.pending_transactions[-1]
        assert txn.transaction_type == "reconciliation"
        assert txn.quantity == 5

    def test_reconcile_sets_balance_and_records_negative_variance(self) -> None:
        location = _make_location()
        cylinder_type_id = uuid.uuid4()
        location.receive_goods(cylinder_type_id, 50, performed_by=uuid.uuid4())

        location.reconcile(cylinder_type_id, "filled", 42, performed_by=uuid.uuid4())

        assert location.balance_of(cylinder_type_id, "filled") == 42
        txn = location.pending_transactions[-1]
        assert txn.transaction_type == "reconciliation"
        assert txn.quantity == 8

    def test_reconcile_with_no_variance_records_no_transaction(self) -> None:
        location = _make_location()
        cylinder_type_id = uuid.uuid4()
        location.receive_goods(cylinder_type_id, 50, performed_by=uuid.uuid4())
        location.clear_pending_transactions()

        location.reconcile(cylinder_type_id, "filled", 50, performed_by=uuid.uuid4())

        assert location.pending_transactions == ()

    def test_reconcile_rejects_negative_actual_quantity(self) -> None:
        location = _make_location()
        with pytest.raises(InvariantViolation, match="negative"):
            location.reconcile(uuid.uuid4(), "filled", -1, performed_by=uuid.uuid4())
