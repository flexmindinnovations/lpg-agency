"""Smoke test for the printing engine — verifies PDF and thermal rendering work."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from lpg.application.printing.models import (
    CustomerInfo,
    InvoicePrintPayload,
    PrintLineItem,
    TenantHeader,
)
from lpg.infrastructure.printing.engine import Xhtml2pdfPrintingEngine


def _make_payload() -> InvoicePrintPayload:
    return InvoicePrintPayload(
        invoice_number="INV-00001234",
        tenant_header=TenantHeader(
            agency_name="Sharma Gas Agency",
            address_line_1="123, MG Road",
            city="Pune",
            state="Maharashtra",
            pincode="411001",
            gstin="27AAPCS1234D1ZN",
            phone="+91-9876543210",
        ),
        customer=CustomerInfo(
            name="Rajesh Kumar",
            consumer_number="C-98765",
            address="45, Shivaji Nagar, Pune 411005",
            phone="+91-9123456789",
        ),
        line_items=[
            PrintLineItem(
                description="14.2 kg Domestic LPG Cylinder",
                quantity=2,
                unit_price=Decimal("900.00"),
                subtotal=Decimal("1800.00"),
                tax_amount=Decimal("324.00"),
                total_amount=Decimal("2124.00"),
            ),
            PrintLineItem(
                description="5 kg Commercial LPG Cylinder",
                quantity=1,
                unit_price=Decimal("1200.00"),
                subtotal=Decimal("1200.00"),
                tax_amount=Decimal("216.00"),
                total_amount=Decimal("1416.00"),
            ),
        ],
        subtotal=Decimal("3000.00"),
        tax_amount=Decimal("540.00"),
        total_amount=Decimal("3540.00"),
        tax_rate_percent=Decimal("18.0"),
        payment_status="issued",
        issued_at=datetime(2026, 8, 14, 10, 30, 0, tzinfo=UTC),
        qr_code_data="lpg-invoice:inv-00001234",
    )


def test_render_invoice_pdf() -> None:
    engine = Xhtml2pdfPrintingEngine()
    payload = _make_payload()
    pdf_bytes = engine.render_invoice_pdf(payload)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000  # A real PDF should be at least a few KB
    assert pdf_bytes[:5] == b"%PDF-"  # PDF magic bytes


def test_render_invoice_thermal() -> None:
    engine = Xhtml2pdfPrintingEngine()
    payload = _make_payload()
    thermal_bytes = engine.render_invoice_thermal(payload)

    text = thermal_bytes.decode("utf-8")
    assert "Sharma Gas Agency" in text
    assert "INV-00001234" in text
    assert "Rajesh Kumar" in text
    assert "14.2 kg Domestic LPG Cylinde" in text  # Truncated to fit 48-char thermal width
    assert "3540.00" in text


def test_generate_qr_code() -> None:
    engine = Xhtml2pdfPrintingEngine()
    qr_bytes = engine.generate_qr_code("https://example.com/verify/inv-123")

    assert isinstance(qr_bytes, bytes)
    assert len(qr_bytes) > 100
    # PNG magic bytes
    assert qr_bytes[:4] == b"\x89PNG"


def test_generate_barcode() -> None:
    engine = Xhtml2pdfPrintingEngine()
    barcode_bytes = engine.generate_barcode("INV00001234")

    assert isinstance(barcode_bytes, bytes)
    assert len(barcode_bytes) > 100
