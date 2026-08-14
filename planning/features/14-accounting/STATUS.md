# Phase 14: Accounting — Status

**Status:** ✅ COMPLETE
**Date Completed:** 2026-08-13

## Summary

Full Accounting bounded context delivered — schema, domain, use cases, REST API, event-driven invoice generation, and frontend UI. Invoices are automatically generated when a `CylinderDelivered` domain event fires after an order delivery.

## What was built

- **Database Schema**: `accounting` schema, `invoice` and `invoice_line` tables with RLS tenant isolation and grants.
- **Domain Model**: `Invoice` aggregate with `InvoiceLine`, `Invoice.generate_for_delivered_order()` factory, and `InvoiceGenerated` domain event.
- **Use Cases**:
  - `GenerateInvoiceForOrderUseCase` — fetches order lines, resolves GST from `TenantConfiguration`, builds invoice lines, persists via `InvoiceRepository`.
  - `GetInvoiceUseCase` — retrieve a single invoice.
  - `ListInvoicesUseCase` — paginated listing with customer/order/status filters.
- **Event-Driven Invoice Generation**:
  - `infrastructure/events/accounting_handlers.py` subscribes `_on_cylinder_delivered` to `CylinderDelivered`.
  - Handler opens its own tenant-scoped session, runs `GenerateInvoiceForOrderUseCase`, and commits atomically.
  - Registered in `app.py` via `register_accounting_handlers`.
  - Idempotent: a second event for the same order is silently skipped (`get_by_order_id` guard).
- **API Endpoints**: `GET /api/v1/invoices`, `GET /api/v1/invoices/{id}` with `invoices:read` RBAC.
- **Frontend UI**: `@lpg/accounting/feature-invoices` — AG Grid invoice list with customer/status filters, detail panel with line breakdown.
- **Unit Tests** (`tests/unit/test_accounting_use_cases.py`): 12 tests covering invoice generation, GST calculation, zero-quantity skip, idempotency guard, missing-order graceful skip, no-config zero-GST, null unit_price, query use cases.

## Quality Metrics

- **766 backend tests passing** (up from 754), `mypy --strict` clean, `ruff` clean, all 5 `import-linter` contracts pass.
- `nx build dashboard` clean, all 19 frontend Jest projects passing.
- Alembic drift-checked.
