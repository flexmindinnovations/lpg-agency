"""Employee aggregate root.

The central HR record for a staff member. Drives the creation of IdentityUser
and is referenced by role-specific aggregates like Driver.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from dataclasses import dataclass

from lpg.domain.common.base import AggregateRoot, DomainEvent, InvariantViolation

# ---------------------------------------------------------------------------
# Domain Events
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EmployeeRegistered(DomainEvent):
    employee_id: uuid.UUID
    tenant_id: uuid.UUID
    branch_id: uuid.UUID
    employee_code: str
    first_name: str
    last_name: str
    phone_number: str
    email: str | None
    role: str


@dataclass(frozen=True, slots=True)
class EmployeeStatusChanged(DomainEvent):
    employee_id: uuid.UUID
    old_status: str
    new_status: str


# ---------------------------------------------------------------------------
# Valid status transitions
# ---------------------------------------------------------------------------

_EMPLOYEE_TRANSITIONS: dict[str, set[str]] = {
    "active": {"on_leave", "inactive"},
    "on_leave": {"active", "inactive"},
    "inactive": set(),
}

EMPLOYEE_STATUSES: frozenset[str] = frozenset(_EMPLOYEE_TRANSITIONS)


# ---------------------------------------------------------------------------
# Aggregate root
# ---------------------------------------------------------------------------


class Employee(AggregateRoot):
    """Employee aggregate root."""

    __slots__ = (
        "_branch_id",
        "_email",
        "_employee_code",
        "_first_name",
        "_last_name",
        "_phone_number",
        "_role",
        "_status",
        "_tenant_id",
    )

    def __init__(
        self,
        *,
        employee_id: uuid.UUID,
        tenant_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_code: str,
        first_name: str,
        last_name: str,
        phone_number: str,
        role: str,
        email: str | None = None,
        status: str = "active",
        version: int = 1,
    ) -> None:
        super().__init__(employee_id, version=version)
        self._tenant_id = tenant_id
        self._branch_id = branch_id

        self._validate_employee_code(employee_code)
        self._employee_code = employee_code

        self._validate_name(first_name, "first_name")
        self._first_name = first_name

        self._validate_name(last_name, "last_name")
        self._last_name = last_name

        self._validate_phone_number(phone_number)
        self._phone_number = phone_number

        self._email = email
        self._role = role

        if status not in EMPLOYEE_STATUSES:
            msg = f"Unknown employee status: '{status}'."
            raise InvariantViolation(msg)
        self._status = status

        self.record_event(
            EmployeeRegistered(
                employee_id=employee_id,
                tenant_id=tenant_id,
                branch_id=branch_id,
                employee_code=employee_code,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                email=email,
                role=role,
            )
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._tenant_id

    @property
    def branch_id(self) -> uuid.UUID:
        return self._branch_id

    @property
    def employee_code(self) -> str:
        return self._employee_code

    @property
    def first_name(self) -> str:
        return self._first_name

    @property
    def last_name(self) -> str:
        return self._last_name

    @property
    def phone_number(self) -> str:
        return self._phone_number

    @property
    def email(self) -> str | None:
        return self._email

    @property
    def role(self) -> str:
        return self._role

    @property
    def status(self) -> str:
        return self._status

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def change_status(self, new_status: str) -> None:
        """Transition the employee to a new status."""
        if new_status not in EMPLOYEE_STATUSES:
            msg = f"Unknown employee status: '{new_status}'."
            raise InvariantViolation(msg)
        allowed = _EMPLOYEE_TRANSITIONS.get(self._status, set())
        if new_status not in allowed:
            msg = (
                f"Employee status transition from '{self._status}' to "
                f"'{new_status}' is not permitted."
            )
            raise InvariantViolation(msg)

        old_status = self._status
        self._status = new_status
        self.record_event(
            EmployeeStatusChanged(
                employee_id=self.id,
                old_status=old_status,
                new_status=new_status,
            )
        )

    # ------------------------------------------------------------------
    # Private validators
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_employee_code(code: str) -> None:
        if not code or not code.strip():
            msg = "Employee code must not be empty."
            raise InvariantViolation(msg)

    @staticmethod
    def _validate_name(name: str, field_name: str) -> None:
        if not name or not name.strip():
            msg = f"{field_name} must not be empty."
            raise InvariantViolation(msg)

    @staticmethod
    def _validate_phone_number(number: str) -> None:
        if not number or not number.strip():
            msg = "Phone number must not be empty."
            raise InvariantViolation(msg)
