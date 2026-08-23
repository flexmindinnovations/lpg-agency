"""Unit tests for Accounting use cases.

Uses mocked repositories — no database required.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from lpg.application.accounting.use_cases import (
    ApproveRefundCommand,
    ApproveRefundUseCase,
    DeclareCashHandoverCommand,
    DeclareCashHandoverUseCase,
    GenerateInvoiceForOrderUseCase,
    GetInvoiceQuery,
    GetInvoiceUseCase,
    ListInvoicesQuery,
    ListInvoicesUseCase,
    RecordPaymentCommand,
    RecordPaymentUseCase,
    RequestRefundCommand,
    RequestRefundUseCase,
)
from lpg.application.common.errors import NotFoundError, ValidationError
from lpg.domain.accounting.cash_handover import CashHandover
from lpg.domain.accounting.credit_note import CreditNote
from lpg.domain.accounting.invoice import Invoice, InvoiceLine
from lpg.domain.order.order import OrderLine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_order_line(
    *,
    quantity_ordered: int = 5,
    quantity_delivered: int = 3,
    unit_price: Decimal | None = Decimal("100.00"),
) -> OrderLine:
    return OrderLine(
        line_id=uuid.uuid4(),
        cylinder_type_id=uuid.uuid4(),
        quantity_ordered=quantity_ordered,
        quantity_delivered=quantity_delivered,
        unit_price=unit_price,
    )


def _make_order(lines: list[OrderLine] | None = None) -> MagicMock:
    order = MagicMock()
    order.id = uuid.uuid4()
    order.customer_id = uuid.uuid4()
    order.lines = lines if lines is not None else [_make_order_line()]
    return order


def _make_tenant_config_entry(value: str) -> MagicMock:
    entry = MagicMock()
    entry.config_value = value
    return entry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_invoice_repo() -> MagicMock:
    repo = MagicMock()
    repo.get_by_order_id = AsyncMock(return_value=None)
    repo.add = AsyncMock()
    repo.save = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.list_invoices = AsyncMock(return_value=[])
    repo.count_invoices = AsyncMock(return_value=0)
    repo.get_outstanding_balance = AsyncMock(return_value=Decimal("0"))
    return repo


@pytest.fixture
def mock_order_repo() -> MagicMock:
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=_make_order())
    return repo


@pytest.fixture
def mock_tenant_config_repo() -> MagicMock:
    repo = MagicMock()
    repo.list_for_tenant_and_key = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_customer_repo() -> MagicMock:
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_invoice_number_sequence() -> MagicMock:
    sequence = MagicMock()
    sequence.next = AsyncMock(return_value="INV-2026-000001")
    return sequence


@pytest.fixture
def mock_credit_note_number_sequence() -> MagicMock:
    sequence = MagicMock()
    sequence.next = AsyncMock(return_value="CRN000001")
    return sequence


@pytest.fixture
def mock_handover_number_sequence() -> MagicMock:
    sequence = MagicMock()
    sequence.next = AsyncMock(return_value="CSH000001")
    return sequence


# ---------------------------------------------------------------------------
# GenerateInvoiceForOrderUseCase
# ---------------------------------------------------------------------------


class TestGenerateInvoiceForOrderUseCase:
    async def test_generates_invoice_for_delivered_order(
        self,
        mock_invoice_repo: MagicMock,
        mock_order_repo: MagicMock,
        mock_tenant_config_repo: MagicMock,
        mock_customer_repo: MagicMock,
        mock_invoice_number_sequence: MagicMock,
    ) -> None:
        """A delivered order with lines produces one invoice saved via the repo."""
        tenant_id = uuid.uuid4()
        order = _make_order(
            lines=[_make_order_line(quantity_delivered=2, unit_price=Decimal("150.00"))]
        )
        mock_order_repo.get_by_id = AsyncMock(return_value=order)

        use_case = GenerateInvoiceForOrderUseCase(
            invoice_repository=mock_invoice_repo,
            order_repository=mock_order_repo,
            tenant_config_repository=mock_tenant_config_repo,
            customer_repository=mock_customer_repo,
            invoice_number_sequence=mock_invoice_number_sequence,
        )
        await use_case.execute(
            tenant_id=tenant_id,
            order_id=order.id,
            delivered_at=datetime.now(UTC),
        )

        mock_invoice_repo.add.assert_called_once()
        saved_invoice: Invoice = mock_invoice_repo.add.call_args[0][0]
        assert saved_invoice.tenant_id == tenant_id
        assert saved_invoice.order_id == order.id
        assert saved_invoice.customer_id == order.customer_id
        assert saved_invoice.status == "issued"
        assert len(saved_invoice.lines) == 1
        assert saved_invoice.lines[0].quantity == 2
        assert saved_invoice.lines[0].unit_price == Decimal("150.00")

    async def test_applies_gst_rate_from_tenant_config(
        self,
        mock_invoice_repo: MagicMock,
        mock_order_repo: MagicMock,
        mock_tenant_config_repo: MagicMock,
        mock_customer_repo: MagicMock,
        mock_invoice_number_sequence: MagicMock,
    ) -> None:
        """GST from tenant configuration is applied to the invoice totals."""
        tenant_id = uuid.uuid4()
        delivered_at = datetime.now(UTC)

        # One line: 4 units x Rs.100.00 = Rs.400 subtotal; 18% GST = Rs.72 tax; total Rs.472
        order = _make_order(
            lines=[_make_order_line(quantity_delivered=4, unit_price=Decimal("100.00"))]
        )
        mock_order_repo.get_by_id = AsyncMock(return_value=order)

        gst_entry = _make_tenant_config_entry("18")
        mock_tenant_config_repo.list_for_tenant_and_key = AsyncMock(return_value=[gst_entry])

        # TenantConfigurationResolver needs the entry to have effective_from / effective_to
        gst_entry.effective_from = datetime(2020, 1, 1, tzinfo=UTC)
        gst_entry.effective_to = None
        gst_entry.config_key = "gst_rate_percent"

        use_case = GenerateInvoiceForOrderUseCase(
            invoice_repository=mock_invoice_repo,
            order_repository=mock_order_repo,
            tenant_config_repository=mock_tenant_config_repo,
            customer_repository=mock_customer_repo,
            invoice_number_sequence=mock_invoice_number_sequence,
        )
        await use_case.execute(
            tenant_id=tenant_id,
            order_id=order.id,
            delivered_at=delivered_at,
        )

        mock_invoice_repo.add.assert_called_once()
        invoice: Invoice = mock_invoice_repo.add.call_args[0][0]
        line = invoice.lines[0]
        assert line.subtotal == Decimal("400.00")
        assert line.tax_amount == Decimal("72.00")
        assert line.total_amount == Decimal("472.00")

    async def test_skips_lines_with_zero_quantity_delivered(
        self,
        mock_invoice_repo: MagicMock,
        mock_order_repo: MagicMock,
        mock_tenant_config_repo: MagicMock,
        mock_customer_repo: MagicMock,
        mock_invoice_number_sequence: MagicMock,
    ) -> None:
        """Lines where quantity_delivered == 0 are excluded from the invoice."""
        order = _make_order(
            lines=[
                _make_order_line(quantity_delivered=0),
                _make_order_line(quantity_delivered=2, unit_price=Decimal("50.00")),
            ]
        )
        mock_order_repo.get_by_id = AsyncMock(return_value=order)

        use_case = GenerateInvoiceForOrderUseCase(
            invoice_repository=mock_invoice_repo,
            order_repository=mock_order_repo,
            tenant_config_repository=mock_tenant_config_repo,
            customer_repository=mock_customer_repo,
            invoice_number_sequence=mock_invoice_number_sequence,
        )
        await use_case.execute(
            tenant_id=uuid.uuid4(),
            order_id=order.id,
            delivered_at=datetime.now(UTC),
        )

        invoice: Invoice = mock_invoice_repo.add.call_args[0][0]
        assert len(invoice.lines) == 1
        assert invoice.lines[0].quantity == 2

    async def test_does_not_generate_invoice_when_all_lines_undelivered(
        self,
        mock_invoice_repo: MagicMock,
        mock_order_repo: MagicMock,
        mock_tenant_config_repo: MagicMock,
        mock_customer_repo: MagicMock,
        mock_invoice_number_sequence: MagicMock,
    ) -> None:
        """If every line has quantity_delivered == 0, no invoice is persisted."""
        order = _make_order(lines=[_make_order_line(quantity_delivered=0)])
        mock_order_repo.get_by_id = AsyncMock(return_value=order)

        use_case = GenerateInvoiceForOrderUseCase(
            invoice_repository=mock_invoice_repo,
            order_repository=mock_order_repo,
            tenant_config_repository=mock_tenant_config_repo,
            customer_repository=mock_customer_repo,
            invoice_number_sequence=mock_invoice_number_sequence,
        )
        await use_case.execute(
            tenant_id=uuid.uuid4(),
            order_id=order.id,
            delivered_at=datetime.now(UTC),
        )

        mock_invoice_repo.add.assert_not_called()

    async def test_is_idempotent_when_invoice_already_exists(
        self,
        mock_invoice_repo: MagicMock,
        mock_order_repo: MagicMock,
        mock_tenant_config_repo: MagicMock,
        mock_customer_repo: MagicMock,
        mock_invoice_number_sequence: MagicMock,
    ) -> None:
        """If an invoice for the order already exists, generation is skipped (idempotency)."""
        mock_invoice_repo.get_by_order_id = AsyncMock(return_value=MagicMock(spec=Invoice))

        use_case = GenerateInvoiceForOrderUseCase(
            invoice_repository=mock_invoice_repo,
            order_repository=mock_order_repo,
            tenant_config_repository=mock_tenant_config_repo,
            customer_repository=mock_customer_repo,
            invoice_number_sequence=mock_invoice_number_sequence,
        )
        await use_case.execute(
            tenant_id=uuid.uuid4(),
            order_id=uuid.uuid4(),
            delivered_at=datetime.now(UTC),
        )

        # Must not fetch the order or persist anything.
        mock_order_repo.get_by_id.assert_not_called()
        mock_invoice_repo.add.assert_not_called()

    async def test_does_not_crash_when_order_not_found(
        self,
        mock_invoice_repo: MagicMock,
        mock_order_repo: MagicMock,
        mock_tenant_config_repo: MagicMock,
        mock_customer_repo: MagicMock,
        mock_invoice_number_sequence: MagicMock,
    ) -> None:
        """If the order is missing (race condition / late event), generation is
        skipped gracefully."""
        mock_order_repo.get_by_id = AsyncMock(return_value=None)

        use_case = GenerateInvoiceForOrderUseCase(
            invoice_repository=mock_invoice_repo,
            order_repository=mock_order_repo,
            tenant_config_repository=mock_tenant_config_repo,
            customer_repository=mock_customer_repo,
            invoice_number_sequence=mock_invoice_number_sequence,
        )
        # Should not raise; logs an error and returns.
        await use_case.execute(
            tenant_id=uuid.uuid4(),
            order_id=uuid.uuid4(),
            delivered_at=datetime.now(UTC),
        )

        mock_invoice_repo.add.assert_not_called()

    async def test_uses_zero_gst_when_no_config_set(
        self,
        mock_invoice_repo: MagicMock,
        mock_order_repo: MagicMock,
        mock_tenant_config_repo: MagicMock,
        mock_customer_repo: MagicMock,
        mock_invoice_number_sequence: MagicMock,
    ) -> None:
        """When no GST rate is configured, tax_amount is 0 and total equals subtotal."""
        order = _make_order(
            lines=[_make_order_line(quantity_delivered=1, unit_price=Decimal("200.00"))]
        )
        mock_order_repo.get_by_id = AsyncMock(return_value=order)
        mock_tenant_config_repo.list_for_tenant_and_key = AsyncMock(return_value=[])

        use_case = GenerateInvoiceForOrderUseCase(
            invoice_repository=mock_invoice_repo,
            order_repository=mock_order_repo,
            tenant_config_repository=mock_tenant_config_repo,
            customer_repository=mock_customer_repo,
            invoice_number_sequence=mock_invoice_number_sequence,
        )
        await use_case.execute(
            tenant_id=uuid.uuid4(),
            order_id=order.id,
            delivered_at=datetime.now(UTC),
        )

        invoice: Invoice = mock_invoice_repo.add.call_args[0][0]
        assert invoice.lines[0].tax_amount == Decimal("0.0")
        assert invoice.lines[0].total_amount == Decimal("200.00")

    async def test_handles_line_with_no_unit_price_as_zero(
        self,
        mock_invoice_repo: MagicMock,
        mock_order_repo: MagicMock,
        mock_tenant_config_repo: MagicMock,
        mock_customer_repo: MagicMock,
        mock_invoice_number_sequence: MagicMock,
    ) -> None:
        """A line with unit_price=None (unconfirmed order) is treated as zero price."""
        order = _make_order(lines=[_make_order_line(quantity_delivered=3, unit_price=None)])
        mock_order_repo.get_by_id = AsyncMock(return_value=order)

        use_case = GenerateInvoiceForOrderUseCase(
            invoice_repository=mock_invoice_repo,
            order_repository=mock_order_repo,
            tenant_config_repository=mock_tenant_config_repo,
            customer_repository=mock_customer_repo,
            invoice_number_sequence=mock_invoice_number_sequence,
        )
        await use_case.execute(
            tenant_id=uuid.uuid4(),
            order_id=order.id,
            delivered_at=datetime.now(UTC),
        )

        invoice: Invoice = mock_invoice_repo.add.call_args[0][0]
        assert invoice.lines[0].subtotal == Decimal("0.0")
        assert invoice.lines[0].total_amount == Decimal("0.0")


# ---------------------------------------------------------------------------
# GetInvoiceUseCase
# ---------------------------------------------------------------------------


class TestGetInvoiceUseCase:
    async def test_returns_invoice_by_id(self, mock_invoice_repo: MagicMock) -> None:
        invoice_id = uuid.uuid4()
        expected = MagicMock(spec=Invoice)
        mock_invoice_repo.get_by_id = AsyncMock(return_value=expected)

        use_case = GetInvoiceUseCase(mock_invoice_repo)
        result = await use_case.execute(GetInvoiceQuery(invoice_id=invoice_id))

        assert result is expected
        mock_invoice_repo.get_by_id.assert_called_once_with(invoice_id)

    async def test_returns_none_when_not_found(self, mock_invoice_repo: MagicMock) -> None:
        mock_invoice_repo.get_by_id = AsyncMock(return_value=None)

        use_case = GetInvoiceUseCase(mock_invoice_repo)
        result = await use_case.execute(GetInvoiceQuery(invoice_id=uuid.uuid4()))

        assert result is None


# ---------------------------------------------------------------------------
# RecordPaymentUseCase
# ---------------------------------------------------------------------------


def _make_invoice(*, total_amount: Decimal = Decimal("236.00")) -> Invoice:
    invoice_line = InvoiceLine(
        line_id=uuid.uuid4(),
        cylinder_type_id=uuid.uuid4(),
        quantity=1,
        unit_price=total_amount,
        subtotal=total_amount,
        tax_amount=Decimal("0"),
        total_amount=total_amount,
    )
    return Invoice(
        invoice_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        invoice_number="INV-2026-000001",
        customer_id=uuid.uuid4(),
        order_id=uuid.uuid4(),
        status="issued",
        subtotal=total_amount,
        tax_amount=Decimal("0"),
        total_amount=total_amount,
        issued_at=datetime.now(UTC),
        lines=[invoice_line],
    )


class TestRecordPaymentUseCase:
    async def test_records_payment_and_saves(
        self, mock_invoice_repo: MagicMock, mock_uow_with_commit: MagicMock
    ) -> None:
        invoice = _make_invoice(total_amount=Decimal("236.00"))
        mock_invoice_repo.get_by_id = AsyncMock(return_value=invoice)
        collected_by = uuid.uuid4()

        use_case = RecordPaymentUseCase(mock_invoice_repo, mock_uow_with_commit)
        result = await use_case.execute(
            RecordPaymentCommand(
                invoice_id=invoice.id,
                method="cash",
                amount=Decimal("236.00"),
                collected_by=collected_by,
                collected_at=datetime.now(UTC),
            )
        )

        assert result is invoice
        assert invoice.status == "paid"
        mock_invoice_repo.save.assert_called_once_with(invoice)
        mock_uow_with_commit.commit.assert_called_once()

    async def test_raises_when_invoice_not_found(
        self, mock_invoice_repo: MagicMock, mock_uow_with_commit: MagicMock
    ) -> None:
        mock_invoice_repo.get_by_id = AsyncMock(return_value=None)
        use_case = RecordPaymentUseCase(mock_invoice_repo, mock_uow_with_commit)

        with pytest.raises(NotFoundError):
            await use_case.execute(
                RecordPaymentCommand(
                    invoice_id=uuid.uuid4(),
                    method="cash",
                    amount=Decimal("1.00"),
                    collected_by=uuid.uuid4(),
                    collected_at=datetime.now(UTC),
                )
            )

        mock_invoice_repo.save.assert_not_called()
        mock_uow_with_commit.commit.assert_not_called()


# ---------------------------------------------------------------------------
# ListInvoicesUseCase
# ---------------------------------------------------------------------------


class TestListInvoicesUseCase:
    async def test_returns_paginated_invoices_with_total(
        self, mock_invoice_repo: MagicMock
    ) -> None:
        invoices = [MagicMock(spec=Invoice), MagicMock(spec=Invoice)]
        mock_invoice_repo.list_invoices = AsyncMock(return_value=invoices)
        mock_invoice_repo.count_invoices = AsyncMock(return_value=2)

        use_case = ListInvoicesUseCase(mock_invoice_repo)
        result, total = await use_case.execute(ListInvoicesQuery(skip=0, limit=10))

        assert result is invoices
        assert total == 2

    async def test_passes_filters_to_repository(self, mock_invoice_repo: MagicMock) -> None:
        customer_id = uuid.uuid4()
        query = ListInvoicesQuery(skip=5, limit=20, customer_id=customer_id, status="issued")

        use_case = ListInvoicesUseCase(mock_invoice_repo)
        await use_case.execute(query)

        mock_invoice_repo.list_invoices.assert_called_once_with(
            skip=5,
            limit=20,
            customer_id=customer_id,
            order_id=None,
            status="issued",
        )


# ---------------------------------------------------------------------------
# DeclareCashHandoverUseCase
# ---------------------------------------------------------------------------


def _make_route(*, tenant_id: uuid.UUID, driver_id: uuid.UUID) -> MagicMock:
    route = MagicMock()
    route.tenant_id = tenant_id
    route.driver_id = driver_id
    return route


@pytest.fixture
def mock_cash_handover_repo() -> MagicMock:
    repo = MagicMock()
    repo.next_id = MagicMock(return_value=uuid.uuid4())
    repo.add = AsyncMock()
    repo.get_expected_cash_for_route = AsyncMock(return_value=Decimal("0"))
    return repo


@pytest.fixture
def mock_route_repo() -> MagicMock:
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_uow_with_commit() -> MagicMock:
    uow = MagicMock()
    uow.commit = AsyncMock()
    return uow


class TestDeclareCashHandoverUseCase:
    async def test_declares_handover_and_saves(
        self,
        mock_cash_handover_repo: MagicMock,
        mock_route_repo: MagicMock,
        mock_uow_with_commit: MagicMock,
        mock_handover_number_sequence: MagicMock,
    ) -> None:
        tenant_id = uuid.uuid4()
        driver_id = uuid.uuid4()
        route_id = uuid.uuid4()
        mock_route_repo.get_by_id.return_value = _make_route(
            tenant_id=tenant_id, driver_id=driver_id
        )
        mock_cash_handover_repo.get_expected_cash_for_route = AsyncMock(
            return_value=Decimal("1000.00")
        )

        use_case = DeclareCashHandoverUseCase(
            mock_cash_handover_repo,
            mock_route_repo,
            mock_uow_with_commit,
            mock_handover_number_sequence,
        )
        command = DeclareCashHandoverCommand(
            driver_id=driver_id,
            route_id=route_id,
            actual_amount=Decimal("850.00"),
            declared_by=driver_id,
        )

        handover = await use_case.execute(command)

        assert isinstance(handover, CashHandover)
        assert handover.tenant_id == tenant_id
        assert handover.expected_amount == Decimal("1000.00")
        assert handover.actual_amount == Decimal("850.00")
        assert handover.shortfall == Decimal("150.00")
        mock_cash_handover_repo.add.assert_called_once_with(handover)
        mock_uow_with_commit.commit.assert_called_once()

    async def test_raises_when_route_not_found(
        self,
        mock_cash_handover_repo: MagicMock,
        mock_route_repo: MagicMock,
        mock_uow_with_commit: MagicMock,
        mock_handover_number_sequence: MagicMock,
    ) -> None:
        mock_route_repo.get_by_id.return_value = None
        use_case = DeclareCashHandoverUseCase(
            mock_cash_handover_repo,
            mock_route_repo,
            mock_uow_with_commit,
            mock_handover_number_sequence,
        )
        command = DeclareCashHandoverCommand(
            driver_id=uuid.uuid4(),
            route_id=uuid.uuid4(),
            actual_amount=Decimal("0"),
            declared_by=uuid.uuid4(),
        )

        with pytest.raises(NotFoundError):
            await use_case.execute(command)

        mock_cash_handover_repo.add.assert_not_called()
        mock_uow_with_commit.commit.assert_not_called()

    async def test_raises_when_route_belongs_to_a_different_driver(
        self,
        mock_cash_handover_repo: MagicMock,
        mock_route_repo: MagicMock,
        mock_uow_with_commit: MagicMock,
        mock_handover_number_sequence: MagicMock,
    ) -> None:
        actual_driver_id = uuid.uuid4()
        someone_elses_driver_id = uuid.uuid4()
        mock_route_repo.get_by_id.return_value = _make_route(
            tenant_id=uuid.uuid4(), driver_id=actual_driver_id
        )
        use_case = DeclareCashHandoverUseCase(
            mock_cash_handover_repo,
            mock_route_repo,
            mock_uow_with_commit,
            mock_handover_number_sequence,
        )
        command = DeclareCashHandoverCommand(
            driver_id=someone_elses_driver_id,
            route_id=uuid.uuid4(),
            actual_amount=Decimal("0"),
            declared_by=someone_elses_driver_id,
        )

        with pytest.raises(NotFoundError):
            await use_case.execute(command)

        mock_cash_handover_repo.add.assert_not_called()


# ---------------------------------------------------------------------------
# RequestRefundUseCase / ApproveRefundUseCase
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_credit_note_repo() -> MagicMock:
    repo = MagicMock()
    repo.next_id = MagicMock(return_value=uuid.uuid4())
    repo.add = AsyncMock()
    repo.save = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    return repo


def _make_paid_invoice(*, amount_paid: Decimal = Decimal("236.00")) -> Invoice:
    invoice = _make_invoice(total_amount=Decimal("236.00"))
    invoice.record_payment(
        payment_id=uuid.uuid4(),
        method="cash",
        amount=amount_paid,
        collected_by=uuid.uuid4(),
        collected_at=datetime.now(UTC),
    )
    return invoice


class TestRequestRefundUseCase:
    async def test_requests_refund_and_saves(
        self,
        mock_credit_note_repo: MagicMock,
        mock_invoice_repo: MagicMock,
        mock_uow_with_commit: MagicMock,
        mock_credit_note_number_sequence: MagicMock,
    ) -> None:
        invoice = _make_paid_invoice(amount_paid=Decimal("236.00"))
        mock_invoice_repo.get_by_id = AsyncMock(return_value=invoice)

        use_case = RequestRefundUseCase(
            mock_credit_note_repo,
            mock_invoice_repo,
            mock_uow_with_commit,
            mock_credit_note_number_sequence,
        )
        credit_note = await use_case.execute(
            RequestRefundCommand(
                invoice_id=invoice.id,
                amount=Decimal("100.00"),
                reason="Damaged cylinder.",
                requested_by=uuid.uuid4(),
            )
        )

        assert isinstance(credit_note, CreditNote)
        assert credit_note.tenant_id == invoice.tenant_id
        assert credit_note.invoice_id == invoice.id
        assert credit_note.amount == Decimal("100.00")
        assert credit_note.is_approved is False
        mock_credit_note_repo.add.assert_called_once_with(credit_note)
        mock_uow_with_commit.commit.assert_called_once()

    async def test_raises_when_invoice_not_found(
        self,
        mock_credit_note_repo: MagicMock,
        mock_invoice_repo: MagicMock,
        mock_uow_with_commit: MagicMock,
        mock_credit_note_number_sequence: MagicMock,
    ) -> None:
        mock_invoice_repo.get_by_id = AsyncMock(return_value=None)
        use_case = RequestRefundUseCase(
            mock_credit_note_repo,
            mock_invoice_repo,
            mock_uow_with_commit,
            mock_credit_note_number_sequence,
        )

        with pytest.raises(NotFoundError):
            await use_case.execute(
                RequestRefundCommand(
                    invoice_id=uuid.uuid4(),
                    amount=Decimal("1.00"),
                    reason="n/a",
                    requested_by=uuid.uuid4(),
                )
            )

        mock_credit_note_repo.add.assert_not_called()

    async def test_rejects_refund_exceeding_amount_paid(
        self,
        mock_credit_note_repo: MagicMock,
        mock_invoice_repo: MagicMock,
        mock_uow_with_commit: MagicMock,
        mock_credit_note_number_sequence: MagicMock,
    ) -> None:
        invoice = _make_paid_invoice(amount_paid=Decimal("100.00"))
        mock_invoice_repo.get_by_id = AsyncMock(return_value=invoice)
        use_case = RequestRefundUseCase(
            mock_credit_note_repo,
            mock_invoice_repo,
            mock_uow_with_commit,
            mock_credit_note_number_sequence,
        )

        with pytest.raises(ValidationError, match="exceeds"):
            await use_case.execute(
                RequestRefundCommand(
                    invoice_id=invoice.id,
                    amount=Decimal("150.00"),
                    reason="n/a",
                    requested_by=uuid.uuid4(),
                )
            )

        mock_credit_note_repo.add.assert_not_called()


class TestApproveRefundUseCase:
    async def test_approves_and_saves(
        self, mock_credit_note_repo: MagicMock, mock_uow_with_commit: MagicMock
    ) -> None:
        invoice_id = uuid.uuid4()
        credit_note = CreditNote.request(
            credit_note_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            invoice_id=invoice_id,
            credit_note_number="CRN000001",
            amount=Decimal("100.00"),
            reason="Damaged cylinder.",
            requested_by=uuid.uuid4(),
        )
        mock_credit_note_repo.get_by_id = AsyncMock(return_value=credit_note)
        approved_by = uuid.uuid4()

        use_case = ApproveRefundUseCase(mock_credit_note_repo, mock_uow_with_commit)
        result = await use_case.execute(
            ApproveRefundCommand(
                invoice_id=invoice_id, credit_note_id=credit_note.id, approved_by=approved_by
            )
        )

        assert result is credit_note
        assert credit_note.is_approved is True
        assert credit_note.approved_by == approved_by
        mock_credit_note_repo.save.assert_called_once_with(credit_note)
        mock_uow_with_commit.commit.assert_called_once()

    async def test_raises_when_credit_note_not_found(
        self, mock_credit_note_repo: MagicMock, mock_uow_with_commit: MagicMock
    ) -> None:
        mock_credit_note_repo.get_by_id = AsyncMock(return_value=None)
        use_case = ApproveRefundUseCase(mock_credit_note_repo, mock_uow_with_commit)

        with pytest.raises(NotFoundError):
            await use_case.execute(
                ApproveRefundCommand(
                    invoice_id=uuid.uuid4(),
                    credit_note_id=uuid.uuid4(),
                    approved_by=uuid.uuid4(),
                )
            )

        mock_credit_note_repo.save.assert_not_called()

    async def test_raises_when_credit_note_belongs_to_a_different_invoice(
        self, mock_credit_note_repo: MagicMock, mock_uow_with_commit: MagicMock
    ) -> None:
        credit_note = CreditNote.request(
            credit_note_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            invoice_id=uuid.uuid4(),
            credit_note_number="CRN000002",
            amount=Decimal("100.00"),
            reason="Damaged cylinder.",
            requested_by=uuid.uuid4(),
        )
        mock_credit_note_repo.get_by_id = AsyncMock(return_value=credit_note)
        use_case = ApproveRefundUseCase(mock_credit_note_repo, mock_uow_with_commit)

        with pytest.raises(NotFoundError):
            await use_case.execute(
                ApproveRefundCommand(
                    invoice_id=uuid.uuid4(),  # a different invoice
                    credit_note_id=credit_note.id,
                    approved_by=uuid.uuid4(),
                )
            )

        mock_credit_note_repo.save.assert_not_called()
