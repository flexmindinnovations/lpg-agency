"""Unit tests for the Vehicle aggregate root.

Validates status transition invariants, capacity/ownership validation,
and domain events without touching the database.
"""

from __future__ import annotations

import uuid

import pytest

from lpg.domain.common.base import InvariantViolation
from lpg.domain.delivery.vehicle import Vehicle, VehicleRegistered, VehicleStatusChanged


def _make_vehicle(**kwargs: object) -> Vehicle:
    defaults = {
        "vehicle_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "branch_id": uuid.uuid4(),
        "registration_number": "MH12AB1234",
        "make": "Tata",
        "model": "Ace",
        "ownership_type": "owned",
        "capacity_units": 10,
    }
    defaults.update(kwargs)
    return Vehicle(**defaults)  # type: ignore[arg-type]


class TestVehicleCreation:
    def test_creates_with_valid_data(self) -> None:
        vehicle = _make_vehicle()
        assert vehicle.registration_number == "MH12AB1234"
        assert vehicle.status == "active"
        assert vehicle.capacity_units == 10

    def test_records_vehicle_registered_event(self) -> None:
        vehicle = _make_vehicle()
        events = vehicle.events
        assert len(events) == 1
        assert isinstance(events[0], VehicleRegistered)

    def test_raises_on_empty_registration_number(self) -> None:
        with pytest.raises(InvariantViolation, match="registration number"):
            _make_vehicle(registration_number="")

    def test_raises_on_empty_make(self) -> None:
        with pytest.raises(InvariantViolation, match="make"):
            _make_vehicle(make="")

    def test_raises_on_empty_model(self) -> None:
        with pytest.raises(InvariantViolation, match="model"):
            _make_vehicle(model="")

    def test_raises_on_zero_capacity(self) -> None:
        with pytest.raises(InvariantViolation, match="capacity_units"):
            _make_vehicle(capacity_units=0)

    def test_raises_on_negative_capacity(self) -> None:
        with pytest.raises(InvariantViolation, match="capacity_units"):
            _make_vehicle(capacity_units=-5)

    def test_raises_on_invalid_ownership_type(self) -> None:
        with pytest.raises(InvariantViolation, match="ownership type"):
            _make_vehicle(ownership_type="leased")

    def test_accepts_all_valid_ownership_types(self) -> None:
        for ot in ("owned", "third_party", "rental", "gig"):
            v = _make_vehicle(ownership_type=ot)
            assert v.ownership_type == ot


class TestVehicleStatusTransitions:
    def test_active_to_maintenance(self) -> None:
        vehicle = _make_vehicle(status="active")
        vehicle.change_status("maintenance")
        assert vehicle.status == "maintenance"

    def test_active_to_inactive(self) -> None:
        vehicle = _make_vehicle(status="active")
        vehicle.change_status("inactive")
        assert vehicle.status == "inactive"

    def test_maintenance_to_active(self) -> None:
        vehicle = _make_vehicle(status="maintenance")
        vehicle.change_status("active")
        assert vehicle.status == "active"

    def test_maintenance_to_inactive(self) -> None:
        vehicle = _make_vehicle(status="maintenance")
        vehicle.change_status("inactive")
        assert vehicle.status == "inactive"

    def test_inactive_cannot_transition(self) -> None:
        vehicle = _make_vehicle(status="inactive")
        with pytest.raises(InvariantViolation, match="not permitted"):
            vehicle.change_status("active")

    def test_active_cannot_go_to_active(self) -> None:
        vehicle = _make_vehicle(status="active")
        with pytest.raises(InvariantViolation, match="not permitted"):
            vehicle.change_status("active")

    def test_unknown_status_raises(self) -> None:
        vehicle = _make_vehicle(status="active")
        with pytest.raises(InvariantViolation, match="Unknown"):
            vehicle.change_status("retired")

    def test_records_status_changed_event(self) -> None:
        vehicle = _make_vehicle(status="active")
        vehicle.clear_events()
        vehicle.change_status("maintenance")
        events = vehicle.events
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, VehicleStatusChanged)
        assert event.old_status == "active"
        assert event.new_status == "maintenance"
