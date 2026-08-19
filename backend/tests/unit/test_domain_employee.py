"""Unit tests for the Employee aggregate root.

Covers constructor validation (code/name/phone/status), the `EmployeeRegistered`
event fired on every construction (including rehydration — the repository is
responsible for clearing it there, not the aggregate), and every
`_EMPLOYEE_TRANSITIONS` edge for `change_status`.
"""

from __future__ import annotations

import uuid

import pytest

from lpg.domain.common.base import InvariantViolation
from lpg.domain.tenant_admin.employee import (
    EMPLOYEE_STATUSES,
    Employee,
    EmployeeRegistered,
    EmployeeStatusChanged,
)


def _make_employee(**kwargs: object) -> Employee:
    defaults: dict[str, object] = {
        "employee_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "branch_id": uuid.uuid4(),
        "employee_code": "EMP0001",
        "first_name": "Asha",
        "last_name": "Verma",
        "phone_number": "+919876543210",
        "role": "driver",
    }
    defaults.update(kwargs)
    return Employee(**defaults)  # type: ignore[arg-type]


class TestEmployeeCreation:
    def test_creates_with_valid_data(self) -> None:
        employee = _make_employee()
        assert employee.employee_code == "EMP0001"
        assert employee.first_name == "Asha"
        assert employee.last_name == "Verma"
        assert employee.status == "active"
        assert employee.email is None

    def test_defaults_to_active_status(self) -> None:
        employee = _make_employee()
        assert employee.status == "active"

    def test_accepts_explicit_status(self) -> None:
        employee = _make_employee(status="on_leave")
        assert employee.status == "on_leave"

    def test_records_employee_registered_event(self) -> None:
        employee = _make_employee(phone_number="+911234567890", email="asha@example.com")
        events = [e for e in employee.events if isinstance(e, EmployeeRegistered)]
        assert len(events) == 1
        event = events[0]
        assert event.employee_id == employee.id
        assert event.employee_code == "EMP0001"
        assert event.phone_number == "+911234567890"
        assert event.email == "asha@example.com"

    def test_rejects_empty_employee_code(self) -> None:
        with pytest.raises(InvariantViolation, match="Employee code"):
            _make_employee(employee_code="   ")

    @pytest.mark.parametrize("field_name", ["first_name", "last_name"])
    def test_rejects_empty_name_fields(self, field_name: str) -> None:
        with pytest.raises(InvariantViolation, match=field_name):
            _make_employee(**{field_name: ""})

    def test_rejects_empty_phone_number(self) -> None:
        with pytest.raises(InvariantViolation, match="Phone number"):
            _make_employee(phone_number="")

    def test_rejects_unknown_status(self) -> None:
        with pytest.raises(InvariantViolation, match="Unknown employee status"):
            _make_employee(status="terminated")


class TestChangeStatus:
    @pytest.mark.parametrize(
        ("from_status", "to_status"),
        [
            ("active", "on_leave"),
            ("active", "inactive"),
            ("on_leave", "active"),
            ("on_leave", "inactive"),
        ],
    )
    def test_allowed_transitions_succeed(self, from_status: str, to_status: str) -> None:
        employee = _make_employee(status=from_status)
        employee.change_status(to_status)
        assert employee.status == to_status

    @pytest.mark.parametrize(
        ("from_status", "to_status"),
        [
            ("active", "active"),
            ("on_leave", "on_leave"),
            ("inactive", "active"),
            ("inactive", "on_leave"),
            ("inactive", "inactive"),
        ],
    )
    def test_disallowed_transitions_raise(self, from_status: str, to_status: str) -> None:
        employee = _make_employee(status=from_status)
        with pytest.raises(InvariantViolation, match="not permitted"):
            employee.change_status(to_status)
        assert employee.status == from_status

    def test_change_status_rejects_unknown_status(self) -> None:
        employee = _make_employee()
        with pytest.raises(InvariantViolation, match="Unknown employee status"):
            employee.change_status("terminated")

    def test_change_status_records_event(self) -> None:
        employee = _make_employee(status="active")
        employee.change_status("on_leave")

        events = [e for e in employee.events if isinstance(e, EmployeeStatusChanged)]
        assert len(events) == 1
        event = events[0]
        assert event.employee_id == employee.id
        assert event.old_status == "active"
        assert event.new_status == "on_leave"

    def test_inactive_is_terminal(self) -> None:
        employee = _make_employee(status="inactive")
        for status in EMPLOYEE_STATUSES:
            with pytest.raises(InvariantViolation):
                employee.change_status(status)
