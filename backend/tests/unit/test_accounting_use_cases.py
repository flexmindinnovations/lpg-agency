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
    GenerateInvoiceForOrderUseCase,
    GetInvoiceQuery,
    GetInvoiceUseCase,
    ListInvoicesQuery,
    ListInvoicesUseCase,
)
from lpg.domain.accounting.invoice import Invoice
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
    repo.get_by_id = AsyncMock(return_value=None)
    repo.list_invoices = AsyncMock(return_value=[])
    repo.count_invoices = AsyncMock(return_value=0)
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


# ---------------------------------------------------------------------------
# GenerateInvoiceForOrderUseCase
# ---------------------------------------------------------------------------


class TestGenerateInvoiceForOrderUseCase:
    async def test_generates_invoice_for_delivered_order(
        self,
        mock_invoice_repo: MagicMock,
        mock_order_repo: MagicMock,
        mock_tenant_config_repo: MagicMock,
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
    ) -> None:
        """If every line has quantity_delivered == 0, no invoice is persisted."""
        order = _make_order(lines=[_make_order_line(quantity_delivered=0)])
        mock_order_repo.get_by_id = AsyncMock(return_value=order)

        use_case = GenerateInvoiceForOrderUseCase(
            invoice_repository=mock_invoice_repo,
            order_repository=mock_order_repo,
            tenant_config_repository=mock_tenant_config_repo,
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
    ) -> None:
        """If an invoice for the order already exists, generation is skipped (idempotency)."""
        mock_invoice_repo.get_by_order_id = AsyncMock(return_value=MagicMock(spec=Invoice))

        use_case = GenerateInvoiceForOrderUseCase(
            invoice_repository=mock_invoice_repo,
            order_repository=mock_order_repo,
            tenant_config_repository=mock_tenant_config_repo,
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
    ) -> None:
        """If the order is missing (race condition / late event), generation is
        skipped gracefully."""
        mock_order_repo.get_by_id = AsyncMock(return_value=None)

        use_case = GenerateInvoiceForOrderUseCase(
            invoice_repository=mock_invoice_repo,
            order_repository=mock_order_repo,
            tenant_config_repository=mock_tenant_config_repo,
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
    ) -> None:
        """A line with unit_price=None (unconfirmed order) is treated as zero price."""
        order = _make_order(lines=[_make_order_line(quantity_delivered=3, unit_price=None)])
        mock_order_repo.get_by_id = AsyncMock(return_value=order)

        use_case = GenerateInvoiceForOrderUseCase(
            invoice_repository=mock_invoice_repo,
            order_repository=mock_order_repo,
            tenant_config_repository=mock_tenant_config_repo,
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
