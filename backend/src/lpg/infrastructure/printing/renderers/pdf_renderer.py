from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader
from xhtml2pdf import pisa

from lpg.config.logging import get_logger
from lpg.infrastructure.printing.renderers.barcode_generator import generate_qr_png

if TYPE_CHECKING:
    from lpg.application.printing.models import InvoicePrintPayload

_logger = get_logger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=True,
)


def render_invoice_pdf(payload: InvoicePrintPayload) -> bytes:
    """Render an invoice to PDF bytes via HTML intermediate."""
    # Generate QR code if data is provided
    qr_b64 = ""
    if payload.qr_code_data:
        qr_bytes = generate_qr_png(payload.qr_code_data, size=150)
        qr_b64 = base64.b64encode(qr_bytes).decode("ascii")

    template = _env.get_template("invoice.html")
    html = template.render(
        payload=payload,
        qr_code_b64=qr_b64,
    )

    result = io.BytesIO()
    pdf_status = pisa.CreatePDF(io.StringIO(html), dest=result)

    if pdf_status.err:
        _logger.error("pdf_render_failed", errors=pdf_status.err)
        msg = f"PDF rendering failed with {pdf_status.err} error(s)"
        raise RuntimeError(msg)

    return result.getvalue()
