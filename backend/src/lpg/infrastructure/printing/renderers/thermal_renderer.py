from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lpg.application.printing.models import InvoicePrintPayload

_LINE_WIDTH_58MM = 32
_LINE_WIDTH_80MM = 48


def render_invoice_thermal(payload: InvoicePrintPayload, *, width: int = _LINE_WIDTH_80MM) -> bytes:
    """Render an invoice as a plain-text thermal receipt.

    Uses simple fixed-width formatting. A future iteration can switch
    to ESC/POS byte-stream commands for richer formatting.
    """
    lines: list[str] = []
    sep = "-" * width

    # Header
    lines.append(payload.tenant_header.agency_name.center(width))
    if payload.tenant_header.address_line_1:
        lines.append(payload.tenant_header.address_line_1.center(width))
    if payload.tenant_header.city or payload.tenant_header.state:
        city_state = f"{payload.tenant_header.city}, {payload.tenant_header.state}".strip(", ")
        lines.append(city_state.center(width))
    if payload.tenant_header.gstin:
        lines.append(f"GSTIN: {payload.tenant_header.gstin}".center(width))
    if payload.tenant_header.phone:
        lines.append(f"Ph: {payload.tenant_header.phone}".center(width))
    lines.append(sep)

    # Invoice info
    lines.append(f"Invoice: {payload.invoice_number}")
    lines.append(f"Date: {payload.issued_at.strftime('%d-%b-%Y %H:%M')}")
    lines.append(f"Status: {payload.payment_status.upper()}")
    lines.append(sep)

    # Customer
    lines.append(f"Customer: {payload.customer.name}")
    if payload.customer.consumer_number:
        lines.append(f"Consumer#: {payload.customer.consumer_number}")
    lines.append(sep)

    # Line items
    # Header row
    desc_w = width - 20  # leave space for qty, amt
    lines.append(f"{'Item':<{desc_w}}{'Qty':>4} {'Amt':>10}")
    lines.append(sep)
    for item in payload.line_items:
        desc = item.description[:desc_w]
        lines.append(f"{desc:<{desc_w}}{item.quantity:>4} {item.total_amount:>10.2f}")
    lines.append(sep)

    # Totals
    label_w = width - 12
    lines.append(f"{'Subtotal:':<{label_w}}{payload.subtotal:>12.2f}")
    lines.append(f"{'Tax:':<{label_w}}{payload.tax_amount:>12.2f}")
    lines.append(f"{'TOTAL:':<{label_w}}{payload.total_amount:>12.2f}")
    lines.append(sep)
    lines.append("Thank you for your business!".center(width))
    lines.append("")

    return "\n".join(lines).encode("utf-8")
