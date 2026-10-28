"""Rendering a print document must not depend on file storage."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from lpg.application.printing.use_cases import (
    DocumentNotFoundError,
    GeneratePrintJobUseCase,
    PrintFormat,
    PrintJobCommand,
    StorageNotConfiguredError,
    UnsupportedDocumentError,
)
from lpg.domain.common.gst import GstSplit
from lpg.infrastructure.printing.engine import Xhtml2pdfPrintingEngine


def _invoice() -> SimpleNamespace:
    cylinder_type_id = uuid.uuid4()
    line = SimpleNamespace(
        cylinder_type_id=cylinder_type_id,
        description="",
        hsn_code="27111900",
        gst_rate_percent=Decimal("0"),
        quantity=2,
        unit_price=Decimal("2000.00"),
        subtotal=Decimal("4000.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("4000.00"),
    )
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        customer_gstin=None,
        invoice_number="INV-2026-000009",
        lines=[line],
        subtotal=Decimal("4000.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("4000.00"),
        place_of_supply_state_code=None,
        is_inter_state=False,
        amount_paid=Decimal("4000.00"),
        balance_due=Decimal("0.00"),
        status="paid",
        issued_at=datetime(2026, 10, 20, tzinfo=UTC),
        tax_split=lambda: GstSplit.of(Decimal("0.00"), inter_state=False),
    )


def _use_case(invoice: SimpleNamespace | None, storage: object | None) -> GeneratePrintJobUseCase:
    invoice_repo = AsyncMock()
    invoice_repo.get_by_id.return_value = invoice
    customer_repo = AsyncMock()
    customer_repo.get_by_id.return_value = None
    cylinder_repo = AsyncMock()
    cylinder_repo.get.return_value = SimpleNamespace(name="Commercial 19kg")
    tenant_repo = AsyncMock()
    tenant_repo.get.return_value = None
    return GeneratePrintJobUseCase(
        printing_engine=Xhtml2pdfPrintingEngine(),
        invoice_repository=invoice_repo,
        customer_repository=customer_repo,
        cylinder_type_repository=cylinder_repo,
        tenant_repository=tenant_repo,
        storage=storage,  # type: ignore[arg-type]
    )


def _command(fmt: PrintFormat, document_type: str = "invoice") -> PrintJobCommand:
    return PrintJobCommand(document_type=document_type, document_id=uuid.uuid4(), output_format=fmt)


async def test_pdf_renders_without_storage() -> None:
    rendered = await _use_case(_invoice(), None).render(_command(PrintFormat.PDF))

    assert rendered.content.startswith(b"%PDF")
    assert rendered.content_type == "application/pdf"
    assert rendered.filename == "INV-2026-000009.pdf"


async def test_thermal_renders_html_without_storage() -> None:
    rendered = await _use_case(_invoice(), None).render(_command(PrintFormat.THERMAL))

    assert b"<html" in rendered.content.lower()
    assert rendered.content_type.startswith("text/html")
    assert rendered.filename == "INV-2026-000009.html"


async def test_unknown_invoice_is_not_found() -> None:
    with pytest.raises(DocumentNotFoundError):
        await _use_case(None, None).render(_command(PrintFormat.PDF))


async def test_unsupported_document_type() -> None:
    with pytest.raises(UnsupportedDocumentError):
        await _use_case(_invoice(), None).render(_command(PrintFormat.PDF, "waybill"))


async def test_stored_job_without_storage_is_a_clear_error() -> None:
    with pytest.raises(StorageNotConfiguredError):
        await _use_case(_invoice(), None).execute(_command(PrintFormat.PDF))


async def test_stored_job_still_uploads_when_storage_exists() -> None:
    storage = MagicMock()
    storage.upload = AsyncMock()
    storage.url = AsyncMock(return_value="https://files.example/x")

    result = await _use_case(_invoice(), storage).execute(_command(PrintFormat.PDF))

    storage.upload.assert_awaited_once()
    assert result.download_url == "https://files.example/x"


async def test_pdf_with_payment_profile_shows_bank_and_upi() -> None:
    from lpg.application.accounting.payment_profile import PaymentProfile

    invoice = _invoice()
    invoice.amount_paid = Decimal("0.00")
    invoice.balance_due = Decimal("4000.00")
    invoice.status = "issued"
    use_case = _use_case(invoice, None)
    profile = PaymentProfile.validated(
        account_holder="Sai Gas Agency",
        bank_name="HDFC Bank",
        account_number="50100123456789",
        ifsc="HDFC0001234",
        branch="Pune",
        upi_id="saigas@okhdfcbank",
        upi_payee_name="",
        invoice_footer_note="Thank you",
    )
    config = SimpleNamespace(config_key="payment_profile", config_value=profile.to_config())
    config_repo = AsyncMock()
    config_repo.list_for_tenant_and_key.return_value = [config]
    config.effective_from = datetime(2026, 1, 1, tzinfo=UTC)
    use_case._tenant_config_repo = config_repo

    pdf = await use_case.render(_command(PrintFormat.PDF))
    thermal = await use_case.render(_command(PrintFormat.THERMAL))

    assert pdf.content.startswith(b"%PDF")
    assert b"saigas@okhdfcbank" in thermal.content
    assert b"50100123456789" in thermal.content
    assert b"HDFC0001234" in thermal.content
