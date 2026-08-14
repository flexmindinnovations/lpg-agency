# Phase 14: Accounting (Backend) Tasks

## Infrastructure & Schema
- [x] Create Alembic migration for `accounting` schema and `invoice` tables
- [x] Integrate `Invoice` model into SQLAlchemy ORM
- [x] Resolve `employee_code` rename migration conflict

## Domain Models
- [x] Define `Invoice` and `InvoiceLine` aggregates
- [x] Implement tenant isolation logic on models

## Use Cases
- [x] Implement `ListInvoicesUseCase`
- [x] Implement `GetInvoiceUseCase`

## API Endpoints
- [x] Implement `GET /api/v1/invoices`
- [x] Implement `GET /api/v1/invoices/{invoice_id}`
- [x] Add RBAC permissions (`invoices:read`)

## Testing
- [x] Write backend unit/integration tests for Invoices
- [x] Fix broken tests caused by `employee_id` referential integrity checks

## Frontend
- [x] Regenerate API client models and endpoints for Invoices
- [x] Create `InvoiceService` data access layer
- [x] Generate `@lpg/accounting/feature-invoices` library
- [x] Create Invoice Dashboard with data grid and detail view
- [x] Add lazy-loaded `/invoices` route
- [x] Wire up navigation sidebar for Invoices
