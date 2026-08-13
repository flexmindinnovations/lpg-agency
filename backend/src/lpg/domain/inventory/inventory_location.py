"""InventoryLocation aggregate root.

Sole aggregate of the inventory bounded context (``01-domain-model.md`` §3).
One instance per Warehouse or Vehicle, tracking a ``(cylinder_type, status)``
balance map. GoodsReceiptNote and ReconciliationRecord are entities of this
aggregate conceptually but are append-only/two-step records with no
in-memory collection to load-and-mutate, so they are built as plain
dataclasses by their own use cases rather than loaded through this root.

docs/data/01-domain-model.md §4.6/§7/§8, docs/data/08-state-machines.md §5
"""

from __future__ import annotations

import uuid  # noqa: TC003
from dataclasses import dataclass

from lpg.domain.common.base import AggregateRoot, DomainEvent, InvariantViolation

# ---------------------------------------------------------------------------
# Domain Events
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GoodsReceived(DomainEvent):
    inventory_location_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    quantity: int
    performed_by: uuid.UUID


@dataclass(frozen=True, slots=True)
class InventoryAdjusted(DomainEvent):
    inventory_location_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    transaction_type: str
    from_status: str | None
    to_status: str
    quantity: int
    performed_by: uuid.UUID


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------


class InsufficientStockError(InvariantViolation):
    """A debit was attempted for more than the tracked balance holds."""

    error_code = "INSUFFICIENT_STOCK"


class InvalidStatusTransitionError(InvariantViolation):
    """The requested ``from_status`` → ``to_status`` move is not permitted."""

    error_code = "INVALID_STATUS_TRANSITION"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOCATION_TYPES: frozenset[str] = frozenset({"warehouse", "vehicle"})

CYLINDER_STATUSES: frozenset[str] = frozenset(
    {"filled", "empty", "damaged", "leakage", "quarantine", "repair", "scrap"}
)

TRANSACTION_TYPES: frozenset[str] = frozenset(
    {
        "grn_receipt",
        "load",
        "unload",
        "delivery",
        "collection",
        "status_change",
        "adjustment",
        "reconciliation",
        "reservation",
        "reservation_release",
    }
)

# Same-location, same-transaction status moves only. `filled⇄empty` is
# deliberately absent: filled→empty happens through record_delivery (a
# different physical unit leaving to the customer), empty→filled only
# through receive_goods (the GRN cycle) — neither is a same-status-pair,
# 1:1 transition (BR-13's worked example: Filled 50→35 delivering 15,
# Empty 10→24 collecting 14 — the two counters move independently).
_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "empty": frozenset({"damaged", "leakage"}),
    "filled": frozenset({"leakage"}),
    "damaged": frozenset({"quarantine"}),
    "leakage": frozenset({"quarantine"}),
    "quarantine": frozenset({"repair", "scrap"}),
    "repair": frozenset({"filled"}),
    "scrap": frozenset(),
}


# ---------------------------------------------------------------------------
# Value object: one row to persist to inventory.inventory_transaction
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class InventoryTransactionRecord:
    """One append-only ``inventory_transaction`` row produced by a mutation.

    Returned via ``InventoryLocation.pending_transactions`` rather than
    derived from domain events: events are dispatched by the Unit of Work
    *after* commit (pub/sub), but transaction rows must be written in the
    *same* database transaction as the balance update they justify.
    """

    transaction_type: str
    cylinder_type_id: uuid.UUID
    from_status: str | None
    to_status: str
    quantity: int
    performed_by: uuid.UUID
    reference_order_id: uuid.UUID | None = None
    reason: str | None = None


# ---------------------------------------------------------------------------
# Aggregate root
# ---------------------------------------------------------------------------


class InventoryLocation(AggregateRoot):
    """A warehouse or vehicle's cylinder inventory, tracked by type and status.

    Business invariants:
    - Balance for any ``(cylinder_type_id, status)`` pair never goes negative
      (``_debit`` raises ``InsufficientStockError`` before it would).
    - Status moves (``change_status``/``adjust``) must follow
      ``_STATUS_TRANSITIONS`` — ``InvalidStatusTransitionError`` otherwise.
    - ``receive_goods``/``unload`` are warehouse-only; ``load``,
      ``record_delivery``, ``record_collection`` are vehicle-only.
    """

    __slots__ = (
        "_balances",
        "_location_ref_id",
        "_location_type",
        "_pending_transactions",
        "_tenant_id",
    )

    def __init__(
        self,
        *,
        inventory_location_id: uuid.UUID,
        tenant_id: uuid.UUID,
        location_type: str,
        location_ref_id: uuid.UUID,
        balances: dict[tuple[uuid.UUID, str], int] | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(inventory_location_id, version=version)
        self._tenant_id = tenant_id

        self._validate_location_type(location_type)
        self._location_type = location_type
        self._location_ref_id = location_ref_id
        self._balances: dict[tuple[uuid.UUID, str], int] = dict(balances or {})
        self._pending_transactions: list[InventoryTransactionRecord] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._tenant_id

    @property
    def location_type(self) -> str:
        return self._location_type

    @property
    def location_ref_id(self) -> uuid.UUID:
        return self._location_ref_id

    @property
    def balances(self) -> dict[tuple[uuid.UUID, str], int]:
        """Read-only snapshot of the current balance map."""
        return dict(self._balances)

    @property
    def pending_transactions(self) -> tuple[InventoryTransactionRecord, ...]:
        """Transaction rows produced since the last ``clear_pending_transactions``."""
        return tuple(self._pending_transactions)

    def balance_of(self, cylinder_type_id: uuid.UUID, status: str) -> int:
        return self._balances.get((cylinder_type_id, status), 0)

    def clear_pending_transactions(self) -> None:
        """Called by the repository once transaction rows have been persisted."""
        self._pending_transactions.clear()

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def receive_goods(
        self, cylinder_type_id: uuid.UUID, quantity: int, *, performed_by: uuid.UUID
    ) -> None:
        """Record a GRN receipt (D-15). Warehouse-only, always credits Filled."""
        self._require_warehouse()
        self._validate_quantity(quantity)
        self._credit(cylinder_type_id, "filled", quantity)
        self._record_transaction(
            "grn_receipt", cylinder_type_id, None, "filled", quantity, performed_by
        )
        self.record_event(
            GoodsReceived(
                inventory_location_id=self.id,
                cylinder_type_id=cylinder_type_id,
                quantity=quantity,
                performed_by=performed_by,
            )
        )

    def unload(
        self,
        cylinder_type_id: uuid.UUID,
        status: str,
        quantity: int,
        *,
        performed_by: uuid.UUID,
    ) -> None:
        """Warehouse side of a load transfer: stock leaves this location."""
        self._require_warehouse()
        self._validate_quantity(quantity)
        self._validate_status(status)
        self._debit(cylinder_type_id, status, quantity)
        self._record_transaction("unload", cylinder_type_id, status, status, quantity, performed_by)

    def load(
        self,
        cylinder_type_id: uuid.UUID,
        status: str,
        quantity: int,
        *,
        performed_by: uuid.UUID,
    ) -> None:
        """Vehicle side of a load transfer: stock arrives at this location."""
        self._require_vehicle()
        self._validate_quantity(quantity)
        self._validate_status(status)
        self._credit(cylinder_type_id, status, quantity)
        self._record_transaction("load", cylinder_type_id, status, status, quantity, performed_by)

    def record_delivery(
        self, cylinder_type_id: uuid.UUID, quantity: int, *, performed_by: uuid.UUID
    ) -> None:
        """Filled cylinders leave the vehicle to a customer. Vehicle-only."""
        self._require_vehicle()
        self._validate_quantity(quantity)
        self._debit(cylinder_type_id, "filled", quantity)
        self._record_transaction(
            "delivery", cylinder_type_id, "filled", "filled", quantity, performed_by
        )

    def record_collection(
        self, cylinder_type_id: uuid.UUID, quantity: int, *, performed_by: uuid.UUID
    ) -> None:
        """Empty cylinders are collected from a customer onto the vehicle. Vehicle-only."""
        self._require_vehicle()
        self._validate_quantity(quantity)
        self._credit(cylinder_type_id, "empty", quantity)
        self._record_transaction(
            "collection", cylinder_type_id, "empty", "empty", quantity, performed_by
        )

    def reserve(
        self,
        cylinder_type_id: uuid.UUID,
        quantity: int,
        *,
        performed_by: uuid.UUID,
        reference_order_id: uuid.UUID | None = None,
    ) -> None:
        """Vehicle stock committed to an assigned Order, not yet delivered.

        Debits Filled the same as ``record_delivery`` — Order Management
        (Phase 10) calls this at assignment (BR-09) rather than waiting until
        delivery, so the reserved quantity is no longer "available" for a
        second order to also claim it.
        """
        self._require_vehicle()
        self._validate_quantity(quantity)
        self._debit(cylinder_type_id, "filled", quantity)
        self._record_transaction(
            "reservation",
            cylinder_type_id,
            "filled",
            "filled",
            quantity,
            performed_by,
            reference_order_id=reference_order_id,
        )

    def release_reservation(
        self,
        cylinder_type_id: uuid.UUID,
        quantity: int,
        *,
        performed_by: uuid.UUID,
        reference_order_id: uuid.UUID | None = None,
    ) -> None:
        """Reverses a still-outstanding ``reserve()`` — order cancellation
        (BR-10) or an over-reservation correction at delivery. Credits Filled
        back; vehicle-only, mirrors ``reserve()``.
        """
        self._require_vehicle()
        self._validate_quantity(quantity)
        self._credit(cylinder_type_id, "filled", quantity)
        self._record_transaction(
            "reservation_release",
            cylinder_type_id,
            "filled",
            "filled",
            quantity,
            performed_by,
            reference_order_id=reference_order_id,
        )

    def change_status(
        self,
        cylinder_type_id: uuid.UUID,
        from_status: str,
        to_status: str,
        quantity: int,
        *,
        performed_by: uuid.UUID,
    ) -> None:
        """Move stock between statuses at this location (e.g. filled→leakage)."""
        self._move(
            cylinder_type_id, from_status, to_status, quantity, "status_change", performed_by
        )

    def adjust(
        self,
        cylinder_type_id: uuid.UUID,
        from_status: str,
        to_status: str,
        quantity: int,
        *,
        performed_by: uuid.UUID,
        reason: str,
    ) -> None:
        """Manual correction, gated by the separate ``inventory:adjust`` permission."""
        self._move(
            cylinder_type_id,
            from_status,
            to_status,
            quantity,
            "adjustment",
            performed_by,
            reason=reason,
        )

    def reconcile(
        self,
        cylinder_type_id: uuid.UUID,
        status: str,
        actual_quantity: int,
        *,
        performed_by: uuid.UUID,
    ) -> None:
        """Set the tracked balance to a physically-counted value.

        Records the delta (if any) as a ``reconciliation`` transaction so the
        "balance updated only within the same transaction as its source"
        invariant holds even for count corrections.
        """
        self._validate_status(status)
        if actual_quantity < 0:
            msg = f"Actual quantity cannot be negative, got {actual_quantity}."
            raise InvariantViolation(msg)

        key = (cylinder_type_id, status)
        expected = self._balances.get(key, 0)
        delta = actual_quantity - expected
        self._balances[key] = actual_quantity
        if delta == 0:
            return
        self._record_transaction(
            "reconciliation", cylinder_type_id, status, status, abs(delta), performed_by
        )

    # ------------------------------------------------------------------
    # Internal mutation helpers
    # ------------------------------------------------------------------

    def _move(
        self,
        cylinder_type_id: uuid.UUID,
        from_status: str,
        to_status: str,
        quantity: int,
        transaction_type: str,
        performed_by: uuid.UUID,
        *,
        reason: str | None = None,
    ) -> None:
        self._validate_quantity(quantity)
        self._validate_status(from_status)
        self._validate_status(to_status)
        allowed = _STATUS_TRANSITIONS.get(from_status, frozenset())
        if to_status not in allowed:
            msg = f"Cannot transition cylinder status from '{from_status}' to '{to_status}'."
            raise InvalidStatusTransitionError(msg, from_status=from_status, to_status=to_status)

        self._debit(cylinder_type_id, from_status, quantity)
        self._credit(cylinder_type_id, to_status, quantity)
        self._record_transaction(
            transaction_type,
            cylinder_type_id,
            from_status,
            to_status,
            quantity,
            performed_by,
            reason=reason,
        )
        self.record_event(
            InventoryAdjusted(
                inventory_location_id=self.id,
                cylinder_type_id=cylinder_type_id,
                transaction_type=transaction_type,
                from_status=from_status,
                to_status=to_status,
                quantity=quantity,
                performed_by=performed_by,
            )
        )

    def _credit(self, cylinder_type_id: uuid.UUID, status: str, quantity: int) -> None:
        key = (cylinder_type_id, status)
        self._balances[key] = self._balances.get(key, 0) + quantity

    def _debit(self, cylinder_type_id: uuid.UUID, status: str, quantity: int) -> None:
        key = (cylinder_type_id, status)
        available = self._balances.get(key, 0)
        if quantity > available:
            msg = (
                f"Insufficient '{status}' stock for cylinder type {cylinder_type_id}: "
                f"requested {quantity}, available {available}."
            )
            raise InsufficientStockError(
                msg,
                cylinder_type_id=str(cylinder_type_id),
                status=status,
                requested=quantity,
                available=available,
            )
        self._balances[key] = available - quantity

    def _record_transaction(
        self,
        transaction_type: str,
        cylinder_type_id: uuid.UUID,
        from_status: str | None,
        to_status: str,
        quantity: int,
        performed_by: uuid.UUID,
        *,
        reason: str | None = None,
        reference_order_id: uuid.UUID | None = None,
    ) -> None:
        self._pending_transactions.append(
            InventoryTransactionRecord(
                transaction_type=transaction_type,
                cylinder_type_id=cylinder_type_id,
                from_status=from_status,
                to_status=to_status,
                quantity=quantity,
                performed_by=performed_by,
                reason=reason,
                reference_order_id=reference_order_id,
            )
        )

    # ------------------------------------------------------------------
    # Guards and validators
    # ------------------------------------------------------------------

    def _require_warehouse(self) -> None:
        if self._location_type != "warehouse":
            msg = "This operation is only valid for a warehouse location."
            raise InvariantViolation(msg)

    def _require_vehicle(self) -> None:
        if self._location_type != "vehicle":
            msg = "This operation is only valid for a vehicle location."
            raise InvariantViolation(msg)

    @staticmethod
    def _validate_location_type(location_type: str) -> None:
        if location_type not in LOCATION_TYPES:
            msg = (
                f"Inventory location type '{location_type}' is not valid. "
                f"Must be one of: {', '.join(sorted(LOCATION_TYPES))}."
            )
            raise InvariantViolation(msg)

    @staticmethod
    def _validate_status(status: str) -> None:
        if status not in CYLINDER_STATUSES:
            msg = (
                f"Cylinder status '{status}' is not valid. "
                f"Must be one of: {', '.join(sorted(CYLINDER_STATUSES))}."
            )
            raise InvariantViolation(msg)

    @staticmethod
    def _validate_quantity(quantity: int) -> None:
        if quantity < 1:
            msg = f"Quantity must be ≥ 1, got {quantity}."
            raise InvariantViolation(msg)
