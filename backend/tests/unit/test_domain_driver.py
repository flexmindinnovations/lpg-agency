"""Unit tests for the Driver aggregate root.

Validates status transition invariants, license validation, and domain events
without touching the database.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from lpg.domain.common.base import InvariantViolation
from lpg.domain.delivery.driver import (
    Driver,
    DriverLicenseUpdated,
    DriverRegistered,
    DriverStatusChanged,
)


def _make_driver(**kwargs: object) -> Driver:
    defaults = {
        "driver_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "branch_id": uuid.uuid4(),
        "employee_code": "EMP-001",
        "license_number": "DL-12345",
    }
    defaults.update(kwargs)
    return Driver(**defaults)  # type: ignore[arg-type]


class TestDriverCreation:
    def test_creates_with_valid_data(self) -> None:
        driver = _make_driver()
        assert driver.employee_code == "EMP-001"
        assert driver.status == "active"
        assert driver.license_expiry_date is None

    def test_records_driver_registered_event(self) -> None:
        driver = _make_driver()
        events = driver.events
        assert len(events) == 1
        assert isinstance(events[0], DriverRegistered)

    def test_raises_on_empty_employee_code(self) -> None:
        with pytest.raises(InvariantViolation, match="employee code"):
            _make_driver(employee_code="")

    def test_raises_on_whitespace_employee_code(self) -> None:
        with pytest.raises(InvariantViolation, match="employee code"):
            _make_driver(employee_code="   ")

    def test_raises_on_empty_license_number(self) -> None:
        with pytest.raises(InvariantViolation, match="license number"):
            _make_driver(license_number="")

    def test_raises_on_past_license_expiry(self) -> None:
        past = datetime.now(UTC).date() - timedelta(days=1)
        with pytest.raises(InvariantViolation, match="expiry date"):
            _make_driver(license_expiry_date=past)

    def test_accepts_future_license_expiry(self) -> None:
        future = datetime.now(UTC).date() + timedelta(days=365)
        driver = _make_driver(license_expiry_date=future)
        assert driver.license_expiry_date == future


class TestDriverStatusTransitions:
    def test_active_to_on_leave(self) -> None:
        driver = _make_driver(status="active")
        driver.change_status("on_leave")
        assert driver.status == "on_leave"

    def test_active_to_inactive(self) -> None:
        driver = _make_driver(status="active")
        driver.change_status("inactive")
        assert driver.status == "inactive"

    def test_on_leave_to_active(self) -> None:
        driver = _make_driver(status="on_leave")
        driver.change_status("active")
        assert driver.status == "active"

    def test_on_leave_to_inactive(self) -> None:
        driver = _make_driver(status="on_leave")
        driver.change_status("inactive")
        assert driver.status == "inactive"

    def test_inactive_cannot_transition(self) -> None:
        driver = _make_driver(status="inactive")
        with pytest.raises(InvariantViolation, match="not permitted"):
            driver.change_status("active")

    def test_active_cannot_go_to_active(self) -> None:
        driver = _make_driver(status="active")
        with pytest.raises(InvariantViolation, match="not permitted"):
            driver.change_status("active")

    def test_unknown_status_raises(self) -> None:
        driver = _make_driver(status="active")
        with pytest.raises(InvariantViolation, match="Unknown"):
            driver.change_status("suspended")

    def test_records_status_changed_event(self) -> None:
        driver = _make_driver(status="active")
        driver.clear_events()
        driver.change_status("on_leave")
        events = driver.events
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, DriverStatusChanged)
        assert event.old_status == "active"
        assert event.new_status == "on_leave"


class TestDriverLicenseUpdate:
    def test_updates_license_number(self) -> None:
        driver = _make_driver()
        future = datetime.now(UTC).date() + timedelta(days=365)
        driver.update_license("DL-99999", future)
        assert driver.license_number == "DL-99999"
        assert driver.license_expiry_date == future

    def test_raises_on_past_expiry_during_update(self) -> None:
        driver = _make_driver()
        past = datetime.now(UTC).date() - timedelta(days=1)
        with pytest.raises(InvariantViolation, match="expiry date"):
            driver.update_license("DL-99999", past)

    def test_records_license_updated_event(self) -> None:
        driver = _make_driver()
        driver.clear_events()
        driver.update_license("DL-NEW", None)
        events = driver.events
        assert len(events) == 1
        assert isinstance(events[0], DriverLicenseUpdated)
