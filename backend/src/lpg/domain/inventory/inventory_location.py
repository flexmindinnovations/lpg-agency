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
        "omc_return",
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

#: The oil marketing companies a distributor receives filled cylinders from
#: and returns empties to. `other` covers a parallel-marketer supplier.
OMC_CODES: frozenset[str] = frozenset({"iocl", "bpcl", "hpcl", "other"})

#: Statuses that can be sent back to the OMC's bottling plant: empties for
#: refilling, and segregated defective cylinders (MDG 2022 cl. 1.4(b) —
#: damaged, leaking or due-for-test cylinders go back to the plant, they are
#: never repaired or filled at the agency).
OMC_RETURNABLE_STATUSES: frozenset[str] = frozenset({"empty", "damaged", "leakage", "quarantine"})

# Same-location, same-transaction status moves only. `filled⇄empty` is
# deliberately absent: filled→empty happens through record_delivery (a
# different physical unit leaving to the customer), empty→filled only
# through receive_goods (the GRN cycle) — neither is a same-status-pair,
# 1:1 transition (BR-13's worked example: Filled 50→35 delivering 15,
# Empty 10→24 collecting 14 — the two counters move independently).
# `filled→damaged` is allowed: a full cylinder found dented or with a
# broken valve guard is damaged without leaking.
_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "empty": frozenset({"damaged", "leakage"}),
    "filled": frozenset({"damaged", "leakage"}),
    "damaged": frozenset({"quarantine"}),
    "leakage": frozenset({"quarantine"}),
    "quarantine": frozenset({"repair", "scrap"}),
    "repair": frozenset({"filled"}),
    "scrap": frozenset(),
}


def _with_reversals(graph: dict[str, frozenset[str]]) -> dict[str, frozenset[str]]:
    reversed_edges = {status: set(targets) for status, targets in graph.items()}
    for source, targets in graph.items():
        for target in targets:
            reversed_edges[target].add(source)
    return {status: frozenset(targets) for status, targets in reversed_edges.items()}


# A manual adjustment corrects a status move, so it may also undo one (a
# leak report that turned out wrong goes back to filled). It still can't
# invent a move that is no step of the cycle — empty→filled stays GRN-only.
_ADJUSTMENT_TRANSITIONS: dict[str, frozenset[str]] = _with_reversals(_STATUS_TRANSITIONS)


def status_change_targets() -> dict[str, frozenset[str]]:
    """Every status → the statuses a routine status change may move it to.
    Published by the API so clients offer only legal targets (one rule,
    owned here)."""
    return dict(_STATUS_TRANSITIONS)


def adjustment_targets() -> dict[str, frozenset[str]]:
    """Every status → the statuses a manual adjustment may move it to."""
    return dict(_ADJUSTMENT_TRANSITIONS)


def signed_balance_changes(
    transaction_type: str, from_status: str | None, to_status: str, quantity: int
) -> tuple[tuple[str, int], ...]:
    """How one ledger row moved the balance: `(status, signed quantity)`
    pairs. The stock register is built from these, so it can never disagree
    with how the aggregate itself applied the row.

    A `reconciliation` row with no `from_status` is a counted surplus; one
    with `from_status` set is a shortage (see `apply_count_variance`).
    """
    if transaction_type in ("grn_receipt", "load", "collection", "reservation_release"):
        return ((to_status, quantity),)
    if transaction_type in ("unload", "delivery", "reservation", "omc_return"):
        return ((to_status, -quantity),)
    if transaction_type == "reconciliation":
        return ((to_status, quantity if from_status is None else -quantity),)
    # status_change / adjustment: one status down, another up.
    return ((from_status or to_status, -quantity), (to_status, quantity))


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
    - Status moves must follow ``_STATUS_TRANSITIONS`` (``change_status``)
      or ``_ADJUSTMENT_TRANSITIONS`` (``adjust``) —
      ``InvalidStatusTransitionError`` otherwise.
    - ``receive_goods``/``unload``/``return_to_omc`` are warehouse-only; ``load``,
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
            cylinder_type_id,
            from_status,
            to_status,
            quantity,
            "status_change",
            performed_by,
            allowed_moves=_STATUS_TRANSITIONS,
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
            allowed_moves=_ADJUSTMENT_TRANSITIONS,
            reason=reason,
        )

    def return_to_omc(
        self,
        cylinder_type_id: uuid.UUID,
        status: str,
        quantity: int,
        *,
        performed_by: uuid.UUID,
        reason: str | None = None,
    ) -> None:
        """Empties (or segregated defective cylinders) leave the warehouse on
        the OMC's truck back to the bottling plant. Warehouse-only."""
        self._require_warehouse()
        self._validate_quantity(quantity)
        self._validate_status(status)
        if status not in OMC_RETURNABLE_STATUSES:
            msg = (
                f"'{status}' cylinders can't be returned to the OMC. Only "
                f"{', '.join(sorted(OMC_RETURNABLE_STATUSES))} stock goes back to the plant."
            )
            raise InvariantViolation(msg, status=status)
        self._debit(cylinder_type_id, status, quantity)
        self._record_transaction(
            "omc_return", cylinder_type_id, status, status, quantity, performed_by, reason=reason
        )

    def apply_count_variance(
        self,
        cylinder_type_id: uuid.UUID,
        status: str,
        variance: int,
        *,
        performed_by: uuid.UUID,
        reason: str | None = None,
    ) -> None:
        """Book an *approved* physical-count variance (D-16).

        Applies the difference the counter found (``actual - expected`` at
        count time) rather than overwriting the balance with the counted
        figure: stock that moved between the count and its approval stays
        correct. A shortage larger than today's balance raises
        ``InsufficientStockError`` — the count is stale and must be redone.

        A surplus is recorded with no ``from_status`` (a pure credit), a
        shortage with ``from_status == to_status`` — see
        ``signed_balance_changes``.
        """
        self._validate_status(status)
        if variance == 0:
            return
        quantity = abs(variance)
        if variance > 0:
            self._credit(cylinder_type_id, status, quantity)
            from_status: str | None = None
        else:
            self._debit(cylinder_type_id, status, quantity)
            from_status = status
        self._record_transaction(
            "reconciliation",
            cylinder_type_id,
            from_status,
            status,
            quantity,
            performed_by,
            reason=reason,
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
        allowed_moves: dict[str, frozenset[str]],
        reason: str | None = None,
    ) -> None:
        self._validate_quantity(quantity)
        self._validate_status(from_status)
        self._validate_status(to_status)
        allowed = allowed_moves.get(from_status, frozenset())
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
