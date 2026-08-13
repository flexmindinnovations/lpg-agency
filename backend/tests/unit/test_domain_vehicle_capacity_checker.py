"""Unit tests for `VehicleCapacityChecker.allocate()` (BR-09/D-08)."""

from __future__ import annotations

import uuid

from lpg.domain.order.vehicle_capacity_checker import VehicleCapacityChecker


def test_full_allocation_when_stock_covers_the_order() -> None:
    cylinder_type_id = uuid.uuid4()
    allocation = VehicleCapacityChecker.allocate(
        vehicle_balances={cylinder_type_id: 10}, lines=[(cylinder_type_id, 4)]
    )
    assert allocation[cylinder_type_id] == (4, 0)


def test_partial_allocation_when_stock_is_insufficient() -> None:
    cylinder_type_id = uuid.uuid4()
    allocation = VehicleCapacityChecker.allocate(
        vehicle_balances={cylinder_type_id: 3}, lines=[(cylinder_type_id, 5)]
    )
    assert allocation[cylinder_type_id] == (3, 2)


def test_zero_availability_backorders_the_full_line() -> None:
    cylinder_type_id = uuid.uuid4()
    allocation = VehicleCapacityChecker.allocate(vehicle_balances={}, lines=[(cylinder_type_id, 2)])
    assert allocation[cylinder_type_id] == (0, 2)


def test_multiple_distinct_cylinder_types_allocate_independently() -> None:
    type_a, type_b = uuid.uuid4(), uuid.uuid4()
    allocation = VehicleCapacityChecker.allocate(
        vehicle_balances={type_a: 10, type_b: 1}, lines=[(type_a, 2), (type_b, 2)]
    )
    assert allocation[type_a] == (2, 0)
    assert allocation[type_b] == (1, 1)
