"""`CylinderUnit` aggregate root — Cylinder Identity (`planning/features/
20-regulatory-compliance`, subsystem 3, PLAN.md's own words: "the deepest
schema change here").

Today, `InventoryLocation` (`domain/inventory/inventory_location.py`) tracks
cylinders only as bulk counts by `(cylinder_type_id, status)` — no per-serial
identity exists anywhere in this codebase. That makes two regulatory
requirements structurally impossible to evidence: Rule 26, Gas Cylinders
Rules 2016 (a cylinder may not be charged/filled when its periodical retest
is due) and MDG 2022 cl. 1.4(b) (due-for-test cylinders must be segregated
and returned to the bottling plant, not filled or delivered) —
`docs/research/feature-gap-analysis.md` R3, D1.

Deliberately mirrors `domain/compliance/scale.py`'s shape (identity + a
compliance-relevant date, both on one aggregate — not split the way
`ComplianceDocument` is split from `Driver`/`Vehicle`, since a cylinder's
test-due date is intrinsic to the unit itself, the same way a scale's
`certificate_expiry_date` is intrinsic to the scale) rather than inventing a
new pattern.

**The exact statutory retest interval is not known.** Rule 35(1) defers to
IS 15975, which prior research never retrieved (`docs/research/feature-gap-
analysis.md` §7, item 2) — the commonly-quoted "5 years" is US DOT/49 CFR,
not Indian LPG cylinders. `test_due_date` is therefore always an explicit,
caller-supplied fact per unit, never computed here from a hardcoded
interval. See `application/compliance/use_cases.py`'s `RecordStatutoryTest
UseCase` for the tenant-configurable *suggestion* (never a silent default).

This is a narrow, additive slice: `CylinderUnit` is a new, independent
registry. It does not touch `InventoryLocation`'s bulk-quantity commands or
any existing GRN/load/delivery/collection/reconciliation flow — wiring
per-unit custody into those bulk flows needs a serial-carrying load
manifest, which doesn't exist yet, and is deferred to a future slice (see
ADR-042).
"""

from __future__ import annotations

import uuid  # noqa: TC003
from dataclasses import dataclass
from datetime import date

from lpg.domain.common.base import AggregateRoot, DomainEvent, InvariantViolation
from lpg.domain.inventory.inventory_location import CYLINDER_STATUSES

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CUSTODY_TYPES: frozenset[str] = frozenset({"warehouse", "vehicle", "customer", "bottling_plant"})

# Own private transition graph — deliberately NOT importing `InventoryLocation
# ._STATUS_TRANSITIONS` (module-private by convention, and it encodes
# bulk-*balance* semantics specifically: that module's own docstring
# explains `filled⇄empty` is absent there because "a different physical
# unit leaving to the customer" doesn't apply to a bulk counter the same
# way it applies to one serialized unit that IS handed over and later
# returned as the very same cylinder). `CYLINDER_STATUSES` itself (the
# public frozenset of condition values) IS imported — one shared
# vocabulary, no reason to fork the *values*, only the graph. Two
# deliberate divergences from the bulk graph:
#   - `filled -> empty` IS modelled here (a single unit really can go
#     from filled to empty and back, unlike a bulk counter).
#   - `repair -> empty`, not `repair -> filled` — a unit coming out of
#     repair is not implicitly re-charged; it re-enters the fillable pool
#     empty and needs an explicit `receive()` (Rule-26-gated) to become
#     filled again, same as any other empty unit.
_CONDITION_TRANSITIONS: dict[str, frozenset[str]] = {
    "filled": frozenset({"empty", "leakage"}),
    "empty": frozenset({"damaged", "leakage"}),
    "damaged": frozenset({"quarantine"}),
    "leakage": frozenset({"quarantine"}),
    "quarantine": frozenset({"repair", "scrap"}),
    "repair": frozenset({"empty"}),
    "scrap": frozenset(),
}

# ---------------------------------------------------------------------------
# Domain events
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CylinderUnitRegistered(DomainEvent):
    cylinder_unit_id: uuid.UUID
    tenant_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    serial_number: str
    qr_code: str


@dataclass(frozen=True, slots=True)
class CylinderStatutoryTestRecorded(DomainEvent):
    cylinder_unit_id: uuid.UUID
    tested_at: date
    due_date: date
    performed_by: uuid.UUID


@dataclass(frozen=True, slots=True)
class CylinderCustodyChanged(DomainEvent):
    cylinder_unit_id: uuid.UUID
    custody_type: str
    custody_ref_id: uuid.UUID | None
    performed_by: uuid.UUID


@dataclass(frozen=True, slots=True)
class CylinderConditionStatusChanged(DomainEvent):
    cylinder_unit_id: uuid.UUID
    from_status: str
    to_status: str
    performed_by: uuid.UUID
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class CylinderReceived(DomainEvent):
    cylinder_unit_id: uuid.UUID
    warehouse_id: uuid.UUID
    performed_by: uuid.UUID


@dataclass(frozen=True, slots=True)
class CylinderRetired(DomainEvent):
    cylinder_unit_id: uuid.UUID
    performed_by: uuid.UUID


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------


class InvalidCylinderConditionTransitionError(InvariantViolation):
    """The requested condition-status move is not permitted."""

    error_code = "INVALID_CYLINDER_CONDITION_TRANSITION"


class CylinderRetiredError(InvariantViolation):
    """A retired unit accepts no further condition/custody mutations —
    Rule 27's lifetime-record requirement means the row stays queryable,
    it just stops changing."""

    error_code = "CYLINDER_RETIRED"


# ---------------------------------------------------------------------------
# Aggregate root
# ---------------------------------------------------------------------------


class CylinderUnit(AggregateRoot):
    """One physical, individually identified cylinder.

    Business invariants:
    - ``serial_number`` must be non-empty (uniqueness is a `(tenant_id,
      serial_number)` DB constraint plus a use-case pre-check — the
      aggregate itself has no visibility into other units, same reasoning
      `Scale`'s asset-tag uniqueness documents).
    - ``condition_status`` must be one of `CYLINDER_STATUSES`; moves follow
      `_CONDITION_TRANSITIONS`.
    - ``custody_ref_id`` is `None` if and only if ``custody_type ==
      'bottling_plant'`` — the one custody kind with no tenant-owned
      location/party to reference.
    - A retired unit (`is_retired`) accepts no further mutation.
    """

    __slots__ = (
        "_condition_status",
        "_custody_ref_id",
        "_custody_type",
        "_cylinder_type_id",
        "_is_retired",
        "_last_tested_at",
        "_manufacture_date",
        "_owner_omc",
        "_qr_code",
        "_serial_number",
        "_tenant_id",
        "_test_due_date",
    )

    def __init__(
        self,
        *,
        cylinder_unit_id: uuid.UUID,
        tenant_id: uuid.UUID,
        cylinder_type_id: uuid.UUID,
        serial_number: str,
        qr_code: str,
        condition_status: str,
        custody_type: str,
        custody_ref_id: uuid.UUID | None = None,
        manufacture_date: date | None = None,
        owner_omc: str | None = None,
        last_tested_at: date | None = None,
        test_due_date: date | None = None,
        is_retired: bool = False,
        version: int = 1,
    ) -> None:
        super().__init__(cylinder_unit_id, version=version)

        self._validate_serial_number(serial_number)
        self._validate_qr_code(qr_code)
        self._validate_condition_status(condition_status)
        self._validate_custody(custody_type, custody_ref_id)

        self._tenant_id = tenant_id
        self._cylinder_type_id = cylinder_type_id
        self._serial_number = serial_number
        self._qr_code = qr_code.strip()
        self._condition_status = condition_status
        self._custody_type = custody_type
        self._custody_ref_id = custody_ref_id
        self._manufacture_date = manufacture_date
        self._owner_omc = owner_omc
        self._last_tested_at = last_tested_at
        self._test_due_date = test_due_date
        self._is_retired = is_retired

        self.record_event(
            CylinderUnitRegistered(
                cylinder_unit_id=cylinder_unit_id,
                tenant_id=tenant_id,
                cylinder_type_id=cylinder_type_id,
                serial_number=serial_number,
                qr_code=self._qr_code,
            )
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._tenant_id

    @property
    def cylinder_type_id(self) -> uuid.UUID:
        return self._cylinder_type_id

    @property
    def serial_number(self) -> str:
        return self._serial_number

    @property
    def qr_code(self) -> str:
        return self._qr_code

    @property
    def condition_status(self) -> str:
        return self._condition_status

    @property
    def custody_type(self) -> str:
        return self._custody_type

    @property
    def custody_ref_id(self) -> uuid.UUID | None:
        return self._custody_ref_id

    @property
    def manufacture_date(self) -> date | None:
        return self._manufacture_date

    @property
    def owner_omc(self) -> str | None:
        return self._owner_omc

    @property
    def last_tested_at(self) -> date | None:
        return self._last_tested_at

    @property
    def test_due_date(self) -> date | None:
        return self._test_due_date

    @property
    def is_retired(self) -> bool:
        return self._is_retired

    def is_due_for_test(self, *, as_of: date) -> bool:
        """A unit with no `test_due_date` on file (never tested) is **not**
        treated as due — a deliberate, documented policy choice so the
        registry stays usable for onboarding existing bulk stock without
        requiring a first test before every unit can even be registered.
        A real gap against Rule 26's intent, not a researched answer — see
        ADR-042's open questions."""
        return self._test_due_date is not None and self._test_due_date <= as_of

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def record_statutory_test(
        self, *, tested_at: date, due_date: date, performed_by: uuid.UUID
    ) -> None:
        """`due_date` is always caller-supplied — never computed here from
        an assumed interval (the actual IS 15975 interval is unconfirmed)."""
        self._require_not_retired()
        self._last_tested_at = tested_at
        self._test_due_date = due_date
        self.record_event(
            CylinderStatutoryTestRecorded(
                cylinder_unit_id=self.id,
                tested_at=tested_at,
                due_date=due_date,
                performed_by=performed_by,
            )
        )

    def move_custody(
        self,
        *,
        custody_type: str,
        custody_ref_id: uuid.UUID | None,
        performed_by: uuid.UUID,
    ) -> None:
        self._require_not_retired()
        self._validate_custody(custody_type, custody_ref_id)
        self._custody_type = custody_type
        self._custody_ref_id = custody_ref_id
        self.record_event(
            CylinderCustodyChanged(
                cylinder_unit_id=self.id,
                custody_type=custody_type,
                custody_ref_id=custody_ref_id,
                performed_by=performed_by,
            )
        )

    def change_condition_status(
        self, *, new_status: str, performed_by: uuid.UUID, reason: str | None = None
    ) -> None:
        self._require_not_retired()
        self._validate_condition_status(new_status)
        allowed = _CONDITION_TRANSITIONS.get(self._condition_status, frozenset())
        if new_status not in allowed:
            msg = (
                f"Cannot transition cylinder condition from '{self._condition_status}' "
                f"to '{new_status}'."
            )
            raise InvalidCylinderConditionTransitionError(
                msg, from_status=self._condition_status, to_status=new_status
            )
        from_status = self._condition_status
        self._condition_status = new_status
        self.record_event(
            CylinderConditionStatusChanged(
                cylinder_unit_id=self.id,
                from_status=from_status,
                to_status=new_status,
                performed_by=performed_by,
                reason=reason,
            )
        )

    def receive(self, *, warehouse_id: uuid.UUID, performed_by: uuid.UUID) -> None:
        """Charges/fills this unit into warehouse stock — only valid from
        `empty` (same "which moves are meaningful" reasoning as
        `_CONDITION_TRANSITIONS`; a unit in `quarantine`/`damaged`/etc.
        must go through `change_condition_status()` back to `empty` first).
        Pure — no clock access. The Rule-26 due-for-test check is an
        **application-layer** concern (`ReceiveCylinderUnitUseCase` calls
        `is_due_for_test()` itself and raises before calling this), not a
        domain invariant — matching `LoadVehicleForRouteUseCase`'s own
        precedent for an MDG-rule block (application-layer check, 409),
        not `Scale`/`InventoryLocation`'s domain-invariant pattern (422)."""
        self._require_not_retired()
        if self._condition_status != "empty":
            msg = (
                f"Cannot receive a cylinder unit whose condition is "
                f"'{self._condition_status}', not 'empty'."
            )
            raise InvalidCylinderConditionTransitionError(
                msg, from_status=self._condition_status, to_status="filled"
            )
        self._condition_status = "filled"
        self.move_custody(
            custody_type="warehouse", custody_ref_id=warehouse_id, performed_by=performed_by
        )
        self.record_event(
            CylinderReceived(
                cylinder_unit_id=self.id, warehouse_id=warehouse_id, performed_by=performed_by
            )
        )

    def retire(self, *, performed_by: uuid.UUID) -> None:
        """Terminal — not the same as `condition_status='scrap'`. A
        scrapped-but-still-tracked unit and a retired-from-the-registry
        unit are different things, and Rule 27's lifetime-record
        requirement means a retired unit's history must stay queryable
        (same reasoning `is_deleted`-style soft-delete uses elsewhere, but
        this is a distinct, permanent business-lifecycle state, not an
        audit-trail delete)."""
        self._require_not_retired()
        self._is_retired = True
        self.record_event(CylinderRetired(cylinder_unit_id=self.id, performed_by=performed_by))

    # ------------------------------------------------------------------
    # Guards and validators
    # ------------------------------------------------------------------

    def _require_not_retired(self) -> None:
        if self._is_retired:
            msg = "This cylinder unit is retired and accepts no further changes."
            raise CylinderRetiredError(msg, cylinder_unit_id=str(self.id))

    @staticmethod
    def _validate_serial_number(serial_number: str) -> None:
        if not serial_number or not serial_number.strip():
            msg = "Cylinder serial number must not be empty."
            raise InvariantViolation(msg)

    @staticmethod
    def _validate_qr_code(qr_code: str) -> None:
        if not qr_code or not qr_code.strip():
            msg = "Cylinder QR code must not be empty."
            raise InvariantViolation(msg)

    @staticmethod
    def _validate_condition_status(condition_status: str) -> None:
        if condition_status not in CYLINDER_STATUSES:
            msg = (
                f"Cylinder condition status '{condition_status}' is not valid. "
                f"Must be one of: {', '.join(sorted(CYLINDER_STATUSES))}."
            )
            raise InvariantViolation(msg)

    @staticmethod
    def _validate_custody(custody_type: str, custody_ref_id: uuid.UUID | None) -> None:
        if custody_type not in CUSTODY_TYPES:
            msg = (
                f"Custody type '{custody_type}' is not valid. "
                f"Must be one of: {', '.join(sorted(CUSTODY_TYPES))}."
            )
            raise InvariantViolation(msg)
        is_bottling_plant = custody_type == "bottling_plant"
        if is_bottling_plant and custody_ref_id is not None:
            msg = "Custody type 'bottling_plant' must not carry a custody_ref_id."
            raise InvariantViolation(msg)
        if not is_bottling_plant and custody_ref_id is None:
            msg = f"Custody type '{custody_type}' requires a custody_ref_id."
            raise InvariantViolation(msg)


def default_test_due_date(tested_at: date, interval_months: int) -> date:
    """Pure helper for `RecordStatutoryTestUseCase`'s *suggested* due date
    — `interval_months` always comes from tenant configuration (see
    `cylinder_statutory_test_interval_months`'s own docstring in
    `domain/tenant/tenant_configuration.py`), never a constant here. The
    caller decides whether to accept the suggestion; this function never
    runs unless a tenant has actually set the config key."""
    if interval_months <= 0:
        msg = f"Test interval months must be positive, got {interval_months}."
        raise InvariantViolation(msg)
    month_index = tested_at.month - 1 + interval_months
    year = tested_at.year + month_index // 12
    month = month_index % 12 + 1
    # Clamp the day for months with fewer days (e.g. 31 Jan + 1 month).
    day = tested_at.day
    while True:
        try:
            return date(year, month, day)
        except ValueError:
            day -= 1
