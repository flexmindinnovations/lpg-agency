"""Smoke test for the printing engine — verifies PDF and thermal rendering work."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from lpg.application.printing.amount_in_words import rupees_in_words
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
            state_code="27",
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
                hsn_code="27111900",
                gst_rate_percent=Decimal("18"),
                quantity=2,
                unit_price=Decimal("900.00"),
                subtotal=Decimal("1800.00"),
                tax_amount=Decimal("324.00"),
                total_amount=Decimal("2124.00"),
            ),
            PrintLineItem(
                description="5 kg Commercial LPG Cylinder",
                hsn_code="27111900",
                gst_rate_percent=Decimal("18"),
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
        cgst_amount=Decimal("270.00"),
        sgst_amount=Decimal("270.00"),
        total_in_words=rupees_in_words(Decimal("3540.00")),
        place_of_supply="27-Maharashtra",
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
    assert "TAX INVOICE" in text
    assert "HSN 27111900  GST 18%" in text
    assert "CGST:" in text
    assert "SGST:" in text
    assert "IGST:" not in text
    assert "Place of supply: 27-Maharashtra" in text


def test_thermal_inter_state_shows_igst_only() -> None:
    payload = _make_payload().model_copy(
        update={
            "is_inter_state": True,
            "cgst_amount": Decimal("0.00"),
            "sgst_amount": Decimal("0.00"),
            "igst_amount": Decimal("540.00"),
        }
    )
    text = Xhtml2pdfPrintingEngine().render_invoice_thermal(payload).decode("utf-8")
    assert "IGST:" in text
    assert "CGST:" not in text


def test_rupees_in_words_uses_indian_numbering() -> None:
    assert rupees_in_words(Decimal("3540.00")) == ("Rupees Three Thousand Five Hundred Forty Only")
    assert rupees_in_words(Decimal("12345678.05")) == (
        "Rupees One Crore Twenty Three Lakh Forty Five Thousand Six Hundred Seventy Eight"
        " and Five Paise Only"
    )
    assert rupees_in_words(Decimal("0")) == "Rupees Zero Only"


def test_render_invoice_thermal_html() -> None:
    engine = Xhtml2pdfPrintingEngine()
    payload = _make_payload()
    html_bytes = engine.render_invoice_thermal_html(payload)

    html_text = html_bytes.decode("utf-8")
    assert html_text.startswith("<!doctype html>")
    assert "Sharma Gas Agency" in html_text
    assert "INV-00001234" in html_text
    assert "Rajesh Kumar" in html_text
    assert "3540.00" in html_text
    assert "window.print()" in html_text
    assert "window.close()" in html_text


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


def test_render_cylinder_label_pdf() -> None:
    import uuid
    from datetime import date

    from lpg.domain.compliance.cylinder_unit import CylinderUnit

    engine = Xhtml2pdfPrintingEngine()
    unit = CylinderUnit(
        cylinder_unit_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        cylinder_type_id=uuid.uuid4(),
        serial_number="CYL-998877",
        qr_code="CYL-DEMO-14KG-998877",
        condition_status="empty",
        custody_type="warehouse",
        custody_ref_id=uuid.uuid4(),
        owner_omc="INDANE",
        test_due_date=date(2028, 12, 31),
    )
    label_pdf = engine.render_cylinder_label_pdf(unit, cylinder_type_name="14.2 kg Domestic")
    assert isinstance(label_pdf, bytes)
    assert len(label_pdf) > 500
    assert label_pdf[:5] == b"%PDF-"
