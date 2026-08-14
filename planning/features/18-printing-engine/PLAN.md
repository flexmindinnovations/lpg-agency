# Phase 18 — Printing Engine

## Plan

Implement the server-rendered, template-based Printing Engine (ADR-010, ADR-016):

1. **Backend Infrastructure**: Jinja2 HTML templates → xhtml2pdf PDF renderer, plain-text thermal renderer, QR/barcode generators
2. **Application Layer**: `PrintingEngine` port, `InvoicePrintPayload` model, `GeneratePrintJobUseCase`
3. **API Layer**: `POST /api/v1/print-jobs` endpoint with RBAC
4. **Frontend**: `PrintingService` + "Print PDF" / "Print Thermal" buttons on Invoice detail

## Technology Decisions
- **xhtml2pdf** over WeasyPrint (no native C dependencies on Windows)
- **qrcode[pil]** + **python-barcode** for code generation
- Template model is renderer-agnostic per ADR-016
