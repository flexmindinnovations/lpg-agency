# 18 — Printing UX

## Purpose
Designs the user experience for printing: Invoice Printing, Thermal Printing, A4, Print Preview, PDF Export, Barcode, QR, margins, page breaks, multi-page reports — implementing the data contracts in docs/data/16-printing-data-model.md.

## 1. Print Entry Points
Every printable document (Invoice, Delivery Receipt, Cash Receipt, Customer Ledger Statement, GST Report) has a consistent Print action placed identically across screens: a Print icon button in the Detail screen's header, plus Ctrl+P as a global shortcut when a printable document is the focused context (`16-keyboard-shortcuts.md`).

## 2. Print Preview
- Print always opens a Print Preview first — never sends directly to a printer/PDF without a preview step, since incorrect pagination or truncated content on a physical receipt is a real business cost.
- Preview renders the exact same PrintPayload (docs/data/16-printing-data-model.md section 1) that the final output uses — preview and final are guaranteed identical, never a simplified mock.
- Preview shows format tabs (A4, Thermal 58mm, Thermal 80mm, PDF) where a document supports multiple formats, so a user can check both before committing.

## 3. Invoice Printing
- Invoice Print Preview highlights the mandatory Tax Breakdown block distinctly (subtle background tint) so staff can visually confirm GST fields are present before printing.
- A Reprint affordance is always available from Invoice Detail (invoices are immutable once issued, so reprinting never risks showing stale/incorrect data).

## 4. Thermal Printing
- Thermal print flow is optimized for speed: a single tap from Delivery Confirmation (Driver App) or Payment Recording triggers direct-to-thermal-printer output (Bluetooth/USB-connected handheld printer) without an intermediate preview step on mobile specifically, since thermal receipts are short, low-stakes, and the Driver persona needs speed over review — a deliberate, documented exception to the always-preview rule in section 2.
- A visible print-status indicator (Printing, Printed, Failed - Retry) confirms the physical print succeeded, since a silently-failed thermal print would otherwise go unnoticed.

## 5. A4 Printing
- A4 documents use standard print margins (20mm top/bottom, 15mm left/right) and a running header/footer (agency logo plus page number) on every page for multi-page documents.
- Print CSS uses explicit page rules and avoids any UI chrome (sidebar, top bar, buttons) in the print output — a dedicated print stylesheet renders only the document content.

## 6. PDF Export
- Every printable document also offers Download PDF as a distinct action from Print (some users want a file to email/archive, not a physical printout) — both actions render from the same PrintPayload and template, guaranteeing PDF and printed output are visually identical.
- PDF export for large multi-page reports is asynchronous (matching the async export-job pattern in docs/data/11-api-contracts.md) — the UI shows a generating-progress state, then a download-ready notification, never a blocking wait for a large report.

## 7. Barcode and QR
- Barcode (invoice reference) and QR (payment or verification) codes render at a minimum size/resolution that remains scannable at typical thermal-print DPI, tested against real thermal printer output during design review, not just verified on-screen.
- QR/Barcode placement is consistent across all receipt/invoice templates (top-right of the header block) so staff always know where to look.

## 8. Margins and Page Breaks
- Multi-page A4 documents use explicit page-break rules so a table row, or a receipt's line-item block, is never split awkwardly across a page boundary — each row/block is treated as an atomic, non-splittable print unit.
- Page breaks always fall between logical sections (never mid-table-row, never mid-signature-block).

## 9. Multi-Page Reports
- Every page of a multi-page report repeats the running header (report title, date range, page number) so a printed report remains identifiable if pages are separated.
- The final page includes a clear end-of-report marker and, for financial reports, a grand-total summary block, so staff can visually confirm they have the complete document.

## Best Practices
- Every print template's mandatory-versus-customizable block boundary is visually indicated in the Tenant Configuration screen's template editor so an Agency Admin customizing branding never accidentally attempts to remove a legally-required field.
- Print Preview and the on-screen Detail view use the exact same data-fetch, eliminating any possibility of the preview showing different data than what's on screen.

## Risks
- Real-world thermal printer driver variance is a testing risk — mitigated by targeting a documented, tested subset of common printer models at launch, with the Driver App's print-status indicator surfacing failures immediately rather than silently.

## Alternatives Considered
- Direct-print (no preview) for all documents including Invoices — rejected; the cost of an incorrect A4 invoice is high enough to justify the preview step, unlike the low-stakes thermal receipt case.

## Future Scalability
- The barcode/QR placement consistency and the block-based template model mean Phase 2's cylinder-level QR label printing (D-36) reuses the same print-preview-and-format-tab UX pattern, not a new printing flow.
