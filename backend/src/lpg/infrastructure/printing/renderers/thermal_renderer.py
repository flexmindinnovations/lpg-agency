from __future__ import annotations

import html
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
    # Amount column is fixed at 12 chars — the same width the totals
    # section below uses for its value column — so both sections' amounts
    # share the same right edge instead of drifting apart.
    amt_w = 12
    desc_w = width - 4 - 1 - amt_w  # leave space for qty + separator + amount
    lines.append(f"{'Item':<{desc_w}}{'Qty':>4} {'Amt':>{amt_w}}")
    lines.append(sep)
    for item in payload.line_items:
        desc = item.description[:desc_w]
        lines.append(f"{desc:<{desc_w}}{item.quantity:>4} {item.total_amount:>{amt_w}.2f}")
    lines.append(sep)

    # Totals
    label_w = width - amt_w
    lines.append(f"{'Subtotal:':<{label_w}}{payload.subtotal:>{amt_w}.2f}")
    lines.append(f"{'Tax:':<{label_w}}{payload.tax_amount:>{amt_w}.2f}")
    lines.append(f"{'TOTAL:':<{label_w}}{payload.total_amount:>{amt_w}.2f}")
    lines.append(sep)
    lines.append("Thank you for your business!".center(width))
    lines.append("")

    return "\n".join(lines).encode("utf-8")


def render_invoice_thermal_html(
    payload: InvoicePrintPayload, *, width: int = _LINE_WIDTH_80MM
) -> bytes:
    """Wrap the plain-text thermal receipt in a minimal, print-ready HTML
    page instead of serving it as a bare `text/plain` file.

    Used two ways from the same pre-signed download URL: opened directly in
    a new browser tab (its own Print/Close toolbar applies), or embedded in
    an `<iframe>` inside the invoices page's preview dialog — a small script
    detects the iframe case (`window.parent !== window`) and hides the
    toolbar, since the host dialog supplies its own Print/Close controls
    there and showing both would be redundant. `window.print()` is also the
    same call that, once a receipt printer is registered as an OS printer
    (driver-based USB/serial printers), lets the browser's print dialog
    target it directly.
    """
    receipt_text = render_invoice_thermal(payload, width=width).decode("utf-8")
    escaped_text = html.escape(receipt_text)
    escaped_title = html.escape(payload.invoice_number)

    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Receipt {escaped_title}</title>
<style>
  :root {{ color-scheme: light; }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 24px 12px;
    background: #f0f0f0;
    display: flex;
    flex-direction: column;
    align-items: center;
    font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
  }}
  .toolbar {{
    display: flex;
    gap: 8px;
    margin-block-end: 16px;
  }}
  button {{
    font: inherit;
    font-size: 14px;
    padding: 8px 16px;
    border-radius: 6px;
    border: 1px solid #ccc;
    background: #fff;
    cursor: pointer;
  }}
  button.primary {{
    background: #162b66;
    border-color: #162b66;
    color: #fff;
  }}
  .receipt {{
    background: #fff;
    padding: 12px;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.15);
    max-width: 100%;
    overflow-x: auto;
  }}
  pre {{
    margin: 0;
    font-family: "Courier New", ui-monospace, monospace;
    font-size: 12px;
    line-height: 1.35;
    /* Never wrap — this is fixed-width column-aligned text (item/qty/amount,
       dashed separators); wrapping would corrupt the alignment. A narrow
       container (e.g. the invoices page's iframe preview) scrolls
       horizontally via `.receipt`'s `overflow-x` instead. */
    white-space: pre;
  }}
  @media print {{
    body {{ background: #fff; padding: 0; }}
    .toolbar {{ display: none; }}
    .receipt {{ box-shadow: none; padding: 0; max-width: none; }}
  }}
  body.embedded .toolbar {{ display: none; }}
  body.embedded {{ padding: 12px; background: #fff; }}
  body.embedded .receipt {{ box-shadow: none; padding: 0; }}
</style>
</head>
<body>
  <div class="toolbar">
    <button type="button" class="primary" onclick="window.print()">Print Receipt</button>
    <button type="button" onclick="window.close()">Close</button>
  </div>
  <div class="receipt"><pre>{escaped_text}</pre></div>
  <script>
    if (window.parent && window.parent !== window) {{
      document.body.classList.add("embedded");
    }}
    // Cross-origin (this page is served from object storage, not the app's
    // own origin) — the host page cannot call `iframe.contentWindow.print()`
    // directly (that throws a SecurityError; only a small allowlist of
    // properties, postMessage included, is reachable across origins). It
    // asks via postMessage instead, and this page prints itself.
    window.addEventListener("message", function (event) {{
      if (event.data && event.data.type === "lpg-thermal-receipt-print") {{
        window.print();
      }}
    }});
  </script>
</body>
</html>
"""
    return document.encode("utf-8")
