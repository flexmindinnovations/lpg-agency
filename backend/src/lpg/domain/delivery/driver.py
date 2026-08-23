"""Driver aggregate root.

Lifecycle:  active → on_leave → active
                   → inactive
            on_leave → inactive

A Driver links to an ``identity.identity_user`` record (optional at
registration, required before the driver can log in to the Driver App).

docs/data/01-domain-model.md §4.9
"""

from __future__ import annotations

import uuid  # noqa: TC003
from dataclasses import dataclass
from datetime import UTC, date, datetime

from lpg.domain.common.base import AggregateRoot, DomainEvent, InvariantViolation

# ---------------------------------------------------------------------------
# Domain Events
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DriverRegistered(DomainEvent):
    driver_id: uuid.UUID
    tenant_id: uuid.UUID
    branch_id: uuid.UUID
    employee_id: uuid.UUID
    license_number: str


@dataclass(frozen=True, slots=True)
class DriverStatusChanged(DomainEvent):
    driver_id: uuid.UUID
    old_status: str
    new_status: str


@dataclass(frozen=True, slots=True)
class DriverLicenseUpdated(DomainEvent):
    driver_id: uuid.UUID
    license_number: str
    license_expiry_date: date | None


@dataclass(frozen=True, slots=True)
class DriverReassigned(DomainEvent):
    driver_id: uuid.UUID
    old_employee_id: uuid.UUID
    new_employee_id: uuid.UUID
    old_branch_id: uuid.UUID
    new_branch_id: uuid.UUID


# ---------------------------------------------------------------------------
# Valid status transitions
# ---------------------------------------------------------------------------

_DRIVER_TRANSITIONS: dict[str, set[str]] = {
    "active": {"on_leave", "inactive"},
    "on_leave": {"active", "inactive"},
    "inactive": set(),
}

DRIVER_STATUSES: frozenset[str] = frozenset(_DRIVER_TRANSITIONS)


# ---------------------------------------------------------------------------
# Aggregate root
# ---------------------------------------------------------------------------


class Driver(AggregateRoot):
    """Driver aggregate root.

    Business invariants:
    - ``license_number`` must be non-empty.
    - ``license_expiry_date``, when provided, must be today or in the future.
    - Status transitions must follow the documented lifecycle.
    """

    __slots__ = (
        "_branch_id",
        "_employee_id",
        "_identity_user_id",
        "_license_expiry_date",
        "_license_number",
        "_status",
        "_tenant_id",
    )

    def __init__(
        self,
        *,
        driver_id: uuid.UUID,
        tenant_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        license_number: str,
        license_expiry_date: date | None = None,
        status: str = "active",
        identity_user_id: uuid.UUID | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(driver_id, version=version)
        self._tenant_id = tenant_id
        self._branch_id = branch_id
        self._identity_user_id = identity_user_id
        self._status = status
        self._employee_id = employee_id

        self._validate_license_number(license_number)
        self._license_number = license_number

        if license_expiry_date is not None:
            self._validate_license_expiry(license_expiry_date)
        self._license_expiry_date = license_expiry_date

        self.record_event(
            DriverRegistered(
                driver_id=driver_id,
                tenant_id=tenant_id,
                branch_id=branch_id,
                employee_id=employee_id,
                license_number=license_number,
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
    def identity_user_id(self) -> uuid.UUID | None:
        return self._identity_user_id

    @property
    def employee_id(self) -> uuid.UUID:
        return self._employee_id

    @property
    def license_number(self) -> str:
        return self._license_number

    @property
    def license_expiry_date(self) -> date | None:
        return self._license_expiry_date

    @property
    def status(self) -> str:
        return self._status

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def change_status(self, new_status: str) -> None:
        """Transition the driver to a new status.

        Raises ``InvariantViolation`` if the transition is not permitted.
        """
        if new_status not in DRIVER_STATUSES:
            msg = f"Unknown driver status: '{new_status}'."
            raise InvariantViolation(msg)
        allowed = _DRIVER_TRANSITIONS.get(self._status, set())
        if new_status not in allowed:
            msg = (
                f"Driver status transition from '{self._status}' to "
                f"'{new_status}' is not permitted."
            )
            raise InvariantViolation(msg)

        old_status = self._status
        self._status = new_status
        self.record_event(
            DriverStatusChanged(
                driver_id=self.id,
                old_status=old_status,
                new_status=new_status,
            )
        )

    def update_license(
        self,
        license_number: str,
        license_expiry_date: date | None,
    ) -> None:
        """Update license details."""
        self._validate_license_number(license_number)
        if license_expiry_date is not None:
            self._validate_license_expiry(license_expiry_date)

        self._license_number = license_number
        self._license_expiry_date = license_expiry_date
        self.record_event(
            DriverLicenseUpdated(
                driver_id=self.id,
                license_number=license_number,
                license_expiry_date=license_expiry_date,
            )
        )

    def link_identity_user(self, identity_user_id: uuid.UUID) -> None:
        """Associate this driver profile with an identity user account."""
        self._identity_user_id = identity_user_id

    def reassign(self, employee_id: uuid.UUID, branch_id: uuid.UUID) -> None:
        """Relink this driver profile to a (possibly different) employee
        and branch.

        A structural identity change, not a plain field edit — recorded as
        its own event (`DriverReassigned`) rather than folded into
        `DriverLicenseUpdated`/`DriverStatusChanged`, so it reads distinctly
        in the audit trail. Application-layer uniqueness (the new
        `employee_id` isn't already linked to a *different* driver) is the
        caller's responsibility, matching `RegisterDriverUseCase`.
        """
        old_employee_id = self._employee_id
        old_branch_id = self._branch_id
        self._employee_id = employee_id
        self._branch_id = branch_id
        self.record_event(
            DriverReassigned(
                driver_id=self.id,
                old_employee_id=old_employee_id,
                new_employee_id=employee_id,
                old_branch_id=old_branch_id,
                new_branch_id=branch_id,
            )
        )

    # ------------------------------------------------------------------
    # Private validators
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_license_number(number: str) -> None:
        if not number or not number.strip():
            msg = "Driver license number must not be empty."
            raise InvariantViolation(msg)

    @staticmethod
    def _validate_license_expiry(expiry: date) -> None:
        today = datetime.now(UTC).date()
        if expiry < today:
            msg = (
                f"License expiry date {expiry.isoformat()} is in the past. "
                "Provide a current or future date."
            )
            raise InvariantViolation(msg)
