"""CylinderLedger aggregate root.

The Cylinder Ledger tracks exactly how many cylinders of which type a customer
is currently holding (their deposit). It does not track empty vs. filled at the
customer site because the agency has no visibility into consumption.
A customer receives a filled cylinder (delivery), which increases their balance.
A customer returns an empty cylinder (collection), which decreases their balance.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from dataclasses import dataclass

from lpg.domain.common.base import AggregateRoot, DomainEvent, InvariantViolation

# ---------------------------------------------------------------------------
# Domain Events
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LedgerTransactionAppended(DomainEvent):
    cylinder_ledger_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    transaction_type: str
    quantity: int  # Signed delta
    balance_after: int
    performed_by: uuid.UUID
    reference_id: uuid.UUID | None


# ---------------------------------------------------------------------------
# Domain Errors
# ---------------------------------------------------------------------------


class InvalidTransactionTypeError(InvariantViolation):
    """The requested transaction type is not permitted."""

    error_code = "INVALID_TRANSACTION_TYPE"


class NegativeBalanceError(InvariantViolation):
    """The attempted transaction would result in a negative customer balance."""

    error_code = "NEGATIVE_BALANCE"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


TRANSACTION_TYPES: frozenset[str] = frozenset(
    {
        "delivery",  # Agency -> Customer (Customer receives cylinders, balance increases)
        "collection",  # Customer -> Agency (Customer returns cylinders, balance decreases)
        "adjustment",  # Manual correction
        "initial_balance",  # Opening balance
    }
)


# ---------------------------------------------------------------------------
# Value object: one row to persist to cylinder_ledger.ledger_transaction
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LedgerTransaction:
    """One append-only ``ledger_transaction`` row produced by a mutation."""

    transaction_type: str
    cylinder_type_id: uuid.UUID
    quantity: int  # Signed delta. Positive = customer receives, Negative = customer returns
    performed_by: uuid.UUID
    reference_id: uuid.UUID | None = None
    reason: str | None = None


# ---------------------------------------------------------------------------
# Aggregate Root
# ---------------------------------------------------------------------------


class CylinderLedger(AggregateRoot):
    """Tracks a customer's cylinder holdings by type.

    Business invariants:
    - Customer balances cannot go negative (cannot return more than they hold).
    - Transaction quantity cannot be zero.
    """

    __slots__ = (
        "_balances",
        "_customer_id",
        "_pending_transactions",
        "_tenant_id",
    )

    def __init__(
        self,
        *,
        cylinder_ledger_id: uuid.UUID,
        tenant_id: uuid.UUID,
        customer_id: uuid.UUID,
        balances: dict[uuid.UUID, int] | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(cylinder_ledger_id, version=version)
        self._tenant_id = tenant_id
        self._customer_id = customer_id
        self._balances: dict[uuid.UUID, int] = dict(balances or {})
        self._pending_transactions: list[LedgerTransaction] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._tenant_id

    @property
    def customer_id(self) -> uuid.UUID:
        return self._customer_id

    @property
    def balances(self) -> dict[uuid.UUID, int]:
        """Read-only snapshot of the current balance map."""
        return dict(self._balances)

    @property
    def pending_transactions(self) -> tuple[LedgerTransaction, ...]:
        """Transaction rows produced since the last ``clear_pending_transactions``."""
        return tuple(self._pending_transactions)

    def balance_of(self, cylinder_type_id: uuid.UUID) -> int:
        return self._balances.get(cylinder_type_id, 0)

    def clear_pending_transactions(self) -> None:
        """Called by the repository once transaction rows have been persisted."""
        self._pending_transactions.clear()

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def record_delivery(
        self,
        cylinder_type_id: uuid.UUID,
        quantity: int,
        *,
        performed_by: uuid.UUID,
        reference_id: uuid.UUID | None = None,
    ) -> None:
        """Customer receives cylinders. Balance increases."""
        if quantity <= 0:
            raise InvariantViolation("Delivery quantity must be > 0.")
        self._append_transaction(
            "delivery", cylinder_type_id, quantity, performed_by, reference_id=reference_id
        )

    def record_collection(
        self,
        cylinder_type_id: uuid.UUID,
        quantity: int,
        *,
        performed_by: uuid.UUID,
        reference_id: uuid.UUID | None = None,
    ) -> None:
        """Customer returns cylinders. Balance decreases."""
        if quantity <= 0:
            raise InvariantViolation("Collection quantity must be > 0.")
        self._append_transaction(
            "collection", cylinder_type_id, -quantity, performed_by, reference_id=reference_id
        )

    def adjust(
        self,
        cylinder_type_id: uuid.UUID,
        delta: int,
        *,
        performed_by: uuid.UUID,
        reason: str,
    ) -> None:
        """Manual adjustment of the customer's balance. Delta can be positive or negative."""
        if delta == 0:
            raise InvariantViolation("Adjustment delta cannot be zero.")
        if not reason:
            raise InvariantViolation("Adjustment requires a reason.")

        self._append_transaction("adjustment", cylinder_type_id, delta, performed_by, reason=reason)

    def set_initial_balance(
        self,
        cylinder_type_id: uuid.UUID,
        quantity: int,
        *,
        performed_by: uuid.UUID,
        reference_id: uuid.UUID | None = None,
    ) -> None:
        """Set the opening balance (e.g. at customer activation/migration)."""
        if quantity <= 0:
            raise InvariantViolation("Initial balance quantity must be > 0.")
        # Only allow setting initial balance if the current balance is exactly 0
        if self.balance_of(cylinder_type_id) != 0:
            raise InvariantViolation("Initial balance can only be set when current balance is 0.")

        self._append_transaction(
            "initial_balance", cylinder_type_id, quantity, performed_by, reference_id=reference_id
        )

    # ------------------------------------------------------------------
    # Internal mutation helpers
    # ------------------------------------------------------------------

    def _append_transaction(
        self,
        transaction_type: str,
        cylinder_type_id: uuid.UUID,
        quantity_delta: int,
        performed_by: uuid.UUID,
        *,
        reference_id: uuid.UUID | None = None,
        reason: str | None = None,
    ) -> None:
        if transaction_type not in TRANSACTION_TYPES:
            msg = f"Invalid transaction type: {transaction_type}"
            raise InvalidTransactionTypeError(msg)

        current_balance = self._balances.get(cylinder_type_id, 0)
        new_balance = current_balance + quantity_delta

        if new_balance < 0:
            msg = (
                f"Insufficient balance for cylinder type {cylinder_type_id}: "
                f"current {current_balance}, attempted delta {quantity_delta}."
            )
            raise NegativeBalanceError(
                msg,
                cylinder_type_id=str(cylinder_type_id),
                current_balance=current_balance,
                delta=quantity_delta,
            )

        self._balances[cylinder_type_id] = new_balance

        transaction = LedgerTransaction(
            transaction_type=transaction_type,
            cylinder_type_id=cylinder_type_id,
            quantity=quantity_delta,
            performed_by=performed_by,
            reference_id=reference_id,
            reason=reason,
        )
        self._pending_transactions.append(transaction)

        self.record_event(
            LedgerTransactionAppended(
                cylinder_ledger_id=self.id,
                cylinder_type_id=cylinder_type_id,
                transaction_type=transaction_type,
                quantity=quantity_delta,
                balance_after=new_balance,
                performed_by=performed_by,
                reference_id=reference_id,
            )
        )
