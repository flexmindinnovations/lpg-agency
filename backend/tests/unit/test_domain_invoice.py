"""Unit tests for the `Invoice`/`InvoiceLine` aggregate.

Covers `InvoiceLine`'s own validation, `Invoice.__init__`'s three
totals-must-match-lines invariants (the ones the `GenerateInvoiceForOrderUseCase`
tests in `test_accounting_use_cases.py` never exercise directly, since that
use case always computes totals *from* the lines), and the
`generate_for_delivered_order` factory's event/status/total-computation
behavior.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from lpg.domain.accounting.invoice import Invoice, InvoiceGenerated, InvoiceLine
from lpg.domain.common.base import InvariantViolation


def _make_line(
    *,
    quantity: int = 2,
    unit_price: Decimal = Decimal("100.00"),
    subtotal: Decimal = Decimal("200.00"),
    tax_amount: Decimal = Decimal("36.00"),
    total_amount: Decimal = Decimal("236.00"),
) -> InvoiceLine:
    return InvoiceLine(
        line_id=uuid.uuid4(),
        cylinder_type_id=uuid.uuid4(),
        quantity=quantity,
        unit_price=unit_price,
        subtotal=subtotal,
        tax_amount=tax_amount,
        total_amount=total_amount,
    )


class TestInvoiceLine:
    def test_creates_with_valid_data(self) -> None:
        line = _make_line()
        assert line.quantity == 2
        assert line.unit_price == Decimal("100.00")

    def test_rejects_zero_quantity(self) -> None:
        with pytest.raises(InvariantViolation, match="quantity must be > 0"):
            _make_line(quantity=0)

    def test_rejects_negative_quantity(self) -> None:
        with pytest.raises(InvariantViolation, match="quantity must be > 0"):
            _make_line(quantity=-1)

    def test_rejects_negative_unit_price(self) -> None:
        with pytest.raises(InvariantViolation, match="unit price cannot be negative"):
            _make_line(unit_price=Decimal("-1.00"))

    def test_allows_zero_unit_price(self) -> None:
        line = _make_line(unit_price=Decimal("0.00"))
        assert line.unit_price == Decimal("0.00")


def _make_invoice(
    *, lines: list[InvoiceLine] | None = None, **kwargs: object
) -> Invoice:
    lines = lines if lines is not None else [_make_line()]
    subtotal = sum((line.subtotal for line in lines), Decimal("0"))
    tax_amount = sum((line.tax_amount for line in lines), Decimal("0"))
    total_amount = sum((line.total_amount for line in lines), Decimal("0"))

    defaults: dict[str, object] = {
        "invoice_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "customer_id": uuid.uuid4(),
        "order_id": uuid.uuid4(),
        "status": "issued",
        "subtotal": subtotal,
        "tax_amount": tax_amount,
        "total_amount": total_amount,
        "issued_at": datetime.now(UTC),
        "lines": lines,
    }
    defaults.update(kwargs)
    return Invoice(**defaults)  # type: ignore[arg-type]


class TestInvoiceCreation:
    def test_creates_with_totals_matching_lines(self) -> None:
        invoice = _make_invoice()
        assert invoice.status == "issued"
        assert len(invoice.lines) == 1

    def test_rejects_invalid_status(self) -> None:
        with pytest.raises(InvariantViolation, match="not a valid invoice status"):
            _make_invoice(status="overdue")

    def test_rejects_empty_lines(self) -> None:
        with pytest.raises(InvariantViolation, match="at least one line"):
            _make_invoice(
                lines=[],
                subtotal=Decimal("0"),
                tax_amount=Decimal("0"),
                total_amount=Decimal("0"),
            )

    def test_rejects_subtotal_mismatch(self) -> None:
        with pytest.raises(InvariantViolation, match="subtotal"):
            _make_invoice(subtotal=Decimal("999.99"))

    def test_rejects_tax_amount_mismatch(self) -> None:
        with pytest.raises(InvariantViolation, match="tax amount"):
            _make_invoice(tax_amount=Decimal("999.99"))

    def test_rejects_total_amount_mismatch(self) -> None:
        with pytest.raises(InvariantViolation, match="total amount"):
            _make_invoice(total_amount=Decimal("999.99"))

    def test_sums_totals_across_multiple_lines(self) -> None:
        lines = [
            _make_line(
                subtotal=Decimal("100"), tax_amount=Decimal("18"), total_amount=Decimal("118")
            ),
            _make_line(
                subtotal=Decimal("50"), tax_amount=Decimal("9"), total_amount=Decimal("59")
            ),
        ]
        invoice = _make_invoice(lines=lines)
        assert invoice.subtotal == Decimal("150")
        assert invoice.tax_amount == Decimal("27")
        assert invoice.total_amount == Decimal("177")


class TestGenerateForDeliveredOrder:
    def test_computes_totals_from_lines(self) -> None:
        lines = [
            _make_line(
                subtotal=Decimal("200"), tax_amount=Decimal("36"), total_amount=Decimal("236")
            )
        ]
        invoice = Invoice.generate_for_delivered_order(
            invoice_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            customer_id=uuid.uuid4(),
            order_id=uuid.uuid4(),
            delivered_at=datetime.now(UTC),
            lines=lines,
        )
        assert invoice.subtotal == Decimal("200")
        assert invoice.tax_amount == Decimal("36")
        assert invoice.total_amount == Decimal("236")

    def test_sets_status_issued(self) -> None:
        invoice = Invoice.generate_for_delivered_order(
            invoice_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            customer_id=uuid.uuid4(),
            order_id=uuid.uuid4(),
            delivered_at=datetime.now(UTC),
            lines=[_make_line()],
        )
        assert invoice.status == "issued"

    def test_records_invoice_generated_event(self) -> None:
        tenant_id = uuid.uuid4()
        order_id = uuid.uuid4()
        customer_id = uuid.uuid4()
        delivered_at = datetime.now(UTC)

        invoice = Invoice.generate_for_delivered_order(
            invoice_id=uuid.uuid4(),
            tenant_id=tenant_id,
            customer_id=customer_id,
            order_id=order_id,
            delivered_at=delivered_at,
            lines=[_make_line()],
        )

        events = [e for e in invoice.events if isinstance(e, InvoiceGenerated)]
        assert len(events) == 1
        event = events[0]
        assert event.invoice_id == invoice.id
        assert event.tenant_id == tenant_id
        assert event.order_id == order_id
        assert event.customer_id == customer_id
        assert event.total_amount == invoice.total_amount
        assert event.issued_at == delivered_at

    def test_rejects_empty_lines(self) -> None:
        with pytest.raises(InvariantViolation, match="without line items"):
            Invoice.generate_for_delivered_order(
                invoice_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                customer_id=uuid.uuid4(),
                order_id=uuid.uuid4(),
                delivered_at=datetime.now(UTC),
                lines=[],
            )
