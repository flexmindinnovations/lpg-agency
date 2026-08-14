# Phase 18 — Printing Engine: Tasks

## Backend
- [x] Add dependencies (jinja2, xhtml2pdf, qrcode, python-barcode)
- [x] Application layer: `PrintingEngine` port, `InvoicePrintPayload` model, `GeneratePrintJobUseCase`
- [x] Infrastructure layer: `Xhtml2pdfPrintingEngine`, PDF renderer, thermal renderer, barcode generator
- [x] Jinja2 HTML invoice template (GST-compliant, inline CSS)
- [x] API router: `POST /api/v1/print-jobs`
- [x] Dependency injection wiring + import-linter exception
- [x] Unit tests: 4 passing (PDF render, thermal render, QR code, barcode)

## Frontend
- [x] `PrintingService` in shared data-access library
- [x] "Print PDF" and "Print Thermal" buttons in Invoice detail drawer
- [x] Frontend build passes

## Future (deferred)
- [ ] Resolve tenant header and customer info from actual repos
- [ ] Additional templates: delivery receipt, cash receipt, GST report
- [ ] ESC/POS byte-stream for richer thermal formatting
- [ ] Async background rendering for large reports
- [ ] Template customization admin UI (BR-31, D-42)
