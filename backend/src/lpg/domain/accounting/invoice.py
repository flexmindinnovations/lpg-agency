"""`Invoice` aggregate root.

Accounting and billing bounded context (`01-domain-model.md` §4.7).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from lpg.domain.common.base import AggregateRoot, DomainEvent, InvariantViolation

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence
    from datetime import datetime


# ---------------------------------------------------------------------------
# Domain Events
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class InvoiceGenerated(DomainEvent):
    """Fired when an invoice is successfully generated (BR-17).
    """

    invoice_id: uuid.UUID
    tenant_id: uuid.UUID
    order_id: uuid.UUID
    customer_id: uuid.UUID
    total_amount: Decimal
    issued_at: datetime


# ---------------------------------------------------------------------------
# Value Objects / Entities
# ---------------------------------------------------------------------------


class InvoiceLine:
    """A single line item within an Invoice.

    Owned exclusively by `Invoice` — never loaded or persisted independently.
    """

    __slots__ = (
        "cylinder_type_id",
        "id",
        "quantity",
        "subtotal",
        "tax_amount",
        "total_amount",
        "unit_price",
    )

    def __init__(
        self,
        line_id: uuid.UUID,
        cylinder_type_id: uuid.UUID,
        quantity: int,
        unit_price: Decimal,
        subtotal: Decimal,
        tax_amount: Decimal,
        total_amount: Decimal,
    ) -> None:
        if quantity <= 0:
            msg = f"Invoice line quantity must be > 0, got {quantity}."
            raise InvariantViolation(msg)
        if unit_price < Decimal("0"):
            msg = f"Invoice line unit price cannot be negative, got {unit_price}."
            raise InvariantViolation(msg)

        self.id = line_id
        self.cylinder_type_id = cylinder_type_id
        self.quantity = quantity
        self.unit_price = unit_price
        self.subtotal = subtotal
        self.tax_amount = tax_amount
        self.total_amount = total_amount


# ---------------------------------------------------------------------------
# Aggregate Root
# ---------------------------------------------------------------------------

INVOICE_STATUSES: frozenset[str] = frozenset(
    {"draft", "issued", "partially_paid", "paid", "cancelled", "refunded"}
)


class Invoice(AggregateRoot):
    """The Invoice aggregate root.

    Business invariants:
    - Generated from a delivered order (BR-17).
    - Contains at least one line item.
    - Financial totals must match the sum of their line items.
    """

    __slots__ = (
        "_customer_id",
        "_issued_at",
        "_lines",
        "_order_id",
        "_status",
        "_subtotal",
        "_tax_amount",
        "_tenant_id",
        "_total_amount",
    )

    def __init__(
        self,
        *,
        invoice_id: uuid.UUID,
        tenant_id: uuid.UUID,
        customer_id: uuid.UUID,
        order_id: uuid.UUID,
        status: str,
        subtotal: Decimal,
        tax_amount: Decimal,
        total_amount: Decimal,
        issued_at: datetime,
        lines: Sequence[InvoiceLine],
        version: int = 1,
    ) -> None:
        super().__init__(invoice_id, version=version)

        if status not in INVOICE_STATUSES:
            msg = f"'{status}' is not a valid invoice status."
            raise InvariantViolation(msg, status=status)
        if not lines:
            msg = "An invoice must have at least one line."
            raise InvariantViolation(msg)

        # Validation: Totals should match lines
        calculated_subtotal = sum((line.subtotal for line in lines), Decimal("0"))
        calculated_tax = sum((line.tax_amount for line in lines), Decimal("0"))
        calculated_total = sum((line.total_amount for line in lines), Decimal("0"))

        if subtotal != calculated_subtotal:
            msg = f"Invoice subtotal ({subtotal}) does not match line items ({calculated_subtotal})."
            raise InvariantViolation(msg)
        if tax_amount != calculated_tax:
            msg = f"Invoice tax amount ({tax_amount}) does not match line items ({calculated_tax})."
            raise InvariantViolation(msg)
        if total_amount != calculated_total:
            msg = f"Invoice total amount ({total_amount}) does not match line items ({calculated_total})."
            raise InvariantViolation(msg)

        self._tenant_id = tenant_id
        self._customer_id = customer_id
        self._order_id = order_id
        self._status = status
        self._subtotal = subtotal
        self._tax_amount = tax_amount
        self._total_amount = total_amount
        self._issued_at = issued_at
        self._lines: list[InvoiceLine] = list(lines)

    @classmethod
    def generate_for_delivered_order(
        cls,
        *,
        invoice_id: uuid.UUID,
        tenant_id: uuid.UUID,
        customer_id: uuid.UUID,
        order_id: uuid.UUID,
        delivered_at: datetime,
        lines: Sequence[InvoiceLine],
    ) -> Invoice:
        """Factory method to generate a new invoice (Issued status) for a delivered order."""
        if not lines:
            msg = "Cannot generate an invoice without line items."
            raise InvariantViolation(msg)

        subtotal = sum((line.subtotal for line in lines), Decimal("0"))
        tax_amount = sum((line.tax_amount for line in lines), Decimal("0"))
        total_amount = sum((line.total_amount for line in lines), Decimal("0"))

        invoice = cls(
            invoice_id=invoice_id,
            tenant_id=tenant_id,
            customer_id=customer_id,
            order_id=order_id,
            status="issued",
            subtotal=subtotal,
            tax_amount=tax_amount,
            total_amount=total_amount,
            issued_at=delivered_at,
            lines=lines,
        )

        invoice.record_event(
            InvoiceGenerated(
                invoice_id=invoice_id,
                tenant_id=tenant_id,
                order_id=order_id,
                customer_id=customer_id,
                total_amount=total_amount,
                issued_at=delivered_at,
            )
        )
        return invoice

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._tenant_id

    @property
    def customer_id(self) -> uuid.UUID:
        return self._customer_id

    @property
    def order_id(self) -> uuid.UUID:
        return self._order_id

    @property
    def status(self) -> str:
        return self._status

    @property
    def subtotal(self) -> Decimal:
        return self._subtotal

    @property
    def tax_amount(self) -> Decimal:
        return self._tax_amount

    @property
    def total_amount(self) -> Decimal:
        return self._total_amount

    @property
    def issued_at(self) -> datetime:
        return self._issued_at

    @property
    def lines(self) -> Sequence[InvoiceLine]:
        return tuple(self._lines)
