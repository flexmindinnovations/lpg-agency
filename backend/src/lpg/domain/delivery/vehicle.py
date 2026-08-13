"""Vehicle aggregate root.

Lifecycle:  active → maintenance → active
                   → inactive
            maintenance → inactive

docs/data/01-domain-model.md §4.10
"""

from __future__ import annotations

import uuid  # noqa: TC003
from dataclasses import dataclass

from lpg.domain.common.base import AggregateRoot, DomainEvent, InvariantViolation

# ---------------------------------------------------------------------------
# Domain Events
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class VehicleRegistered(DomainEvent):
    vehicle_id: uuid.UUID
    tenant_id: uuid.UUID
    branch_id: uuid.UUID
    registration_number: str
    ownership_type: str
    capacity_units: int


@dataclass(frozen=True, slots=True)
class VehicleStatusChanged(DomainEvent):
    vehicle_id: uuid.UUID
    old_status: str
    new_status: str


# ---------------------------------------------------------------------------
# Valid status transitions
# ---------------------------------------------------------------------------

_VEHICLE_TRANSITIONS: dict[str, set[str]] = {
    "active": {"maintenance", "inactive"},
    "maintenance": {"active", "inactive"},
    "inactive": set(),
}

VEHICLE_STATUSES: frozenset[str] = frozenset(_VEHICLE_TRANSITIONS)

VEHICLE_OWNERSHIP_TYPES: frozenset[str] = frozenset({"owned", "third_party", "rental", "gig"})


# ---------------------------------------------------------------------------
# Aggregate root
# ---------------------------------------------------------------------------


class Vehicle(AggregateRoot):
    """Vehicle aggregate root.

    Business invariants:
    - ``registration_number`` must be non-empty (uniqueness per tenant is
      application-layer).
    - ``capacity_units`` must be ≥ 1.
    - ``ownership_type`` must be one of ``owned | third_party | rental | gig``.
    - Status transitions must follow the documented lifecycle.
    """

    __slots__ = (
        "_branch_id",
        "_capacity_units",
        "_make",
        "_model",
        "_ownership_type",
        "_registration_number",
        "_status",
        "_tenant_id",
    )

    def __init__(
        self,
        *,
        vehicle_id: uuid.UUID,
        tenant_id: uuid.UUID,
        branch_id: uuid.UUID,
        registration_number: str,
        make: str,
        model: str,
        ownership_type: str = "owned",
        capacity_units: int,
        status: str = "active",
        version: int = 1,
    ) -> None:
        super().__init__(vehicle_id, version=version)
        self._tenant_id = tenant_id
        self._branch_id = branch_id

        self._validate_registration_number(registration_number)
        self._registration_number = registration_number

        self._validate_make_model(make, model)
        self._make = make
        self._model = model

        self._validate_ownership_type(ownership_type)
        self._ownership_type = ownership_type

        self._validate_capacity_units(capacity_units)
        self._capacity_units = capacity_units

        self._status = status

        self.record_event(
            VehicleRegistered(
                vehicle_id=vehicle_id,
                tenant_id=tenant_id,
                branch_id=branch_id,
                registration_number=registration_number,
                ownership_type=ownership_type,
                capacity_units=capacity_units,
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
    def registration_number(self) -> str:
        return self._registration_number

    @property
    def make(self) -> str:
        return self._make

    @property
    def model(self) -> str:
        return self._model

    @property
    def ownership_type(self) -> str:
        return self._ownership_type

    @property
    def capacity_units(self) -> int:
        return self._capacity_units

    @property
    def status(self) -> str:
        return self._status

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def change_status(self, new_status: str) -> None:
        """Transition vehicle to a new status.

        Raises ``InvariantViolation`` if the transition is not permitted.
        """
        if new_status not in VEHICLE_STATUSES:
            msg = f"Unknown vehicle status: '{new_status}'."
            raise InvariantViolation(msg)
        allowed = _VEHICLE_TRANSITIONS.get(self._status, set())
        if new_status not in allowed:
            msg = (
                f"Vehicle status transition from '{self._status}' to "
                f"'{new_status}' is not permitted."
            )
            raise InvariantViolation(msg)

        old_status = self._status
        self._status = new_status
        self.record_event(
            VehicleStatusChanged(
                vehicle_id=self.id,
                old_status=old_status,
                new_status=new_status,
            )
        )

    # ------------------------------------------------------------------
    # Private validators
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_registration_number(number: str) -> None:
        if not number or not number.strip():
            msg = "Vehicle registration number must not be empty."
            raise InvariantViolation(msg)

    @staticmethod
    def _validate_make_model(make: str, model: str) -> None:
        if not make or not make.strip():
            msg = "Vehicle make must not be empty."
            raise InvariantViolation(msg)
        if not model or not model.strip():
            msg = "Vehicle model must not be empty."
            raise InvariantViolation(msg)

    @staticmethod
    def _validate_ownership_type(ownership_type: str) -> None:
        if ownership_type not in VEHICLE_OWNERSHIP_TYPES:
            msg = (
                f"Vehicle ownership type '{ownership_type}' is not valid. "
                f"Must be one of: {', '.join(sorted(VEHICLE_OWNERSHIP_TYPES))}."
            )
            raise InvariantViolation(msg)

    @staticmethod
    def _validate_capacity_units(capacity_units: int) -> None:
        if capacity_units < 1:
            msg = f"Vehicle capacity_units must be ≥ 1, got {capacity_units}."
            raise InvariantViolation(msg)
