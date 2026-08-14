from __future__ import annotations

from typing import TYPE_CHECKING

from lpg.application.printing.ports import PrintingEngine
from lpg.infrastructure.printing.renderers.barcode_generator import (
    generate_barcode_png,
    generate_qr_png,
)
from lpg.infrastructure.printing.renderers.pdf_renderer import (
    render_invoice_pdf as _render_invoice_pdf,
)
from lpg.infrastructure.printing.renderers.thermal_renderer import (
    render_invoice_thermal as _render_invoice_thermal,
)

if TYPE_CHECKING:
    from lpg.application.printing.models import InvoicePrintPayload


class Xhtml2pdfPrintingEngine(PrintingEngine):
    """Concrete printing engine using xhtml2pdf for PDF and plain-text for thermal."""

    def render_invoice_pdf(self, payload: InvoicePrintPayload) -> bytes:
        return _render_invoice_pdf(payload)

    def render_invoice_thermal(self, payload: InvoicePrintPayload) -> bytes:
        return _render_invoice_thermal(payload)

    def generate_qr_code(self, data: str, *, size: int = 200) -> bytes:
        return generate_qr_png(data, size=size)

    def generate_barcode(self, data: str) -> bytes:
        return generate_barcode_png(data)
