# Phase 14: Accounting (Backend)

## Objective
Implement the backend foundation for the Accounting bounded context, focusing specifically on Invoicing. This includes the data models, repository, read-only use cases, and REST endpoints for invoices, setting the stage for future billing, payments, and PDF generation.

## Scope
- Database Schema (`accounting`)
- `Invoice` and `InvoiceLine` aggregates/models
- Tenant-isolated Repositories for Invoices
- `GetInvoiceUseCase` and `ListInvoicesUseCase`
- REST API Endpoints (`/api/v1/invoices`) with `invoices:read` RBAC
- Tests and Validation

## Out of Scope
- Frontend UI (planned for next immediate step)
- Payment Processing and Credit Notes (deferred to later billing phases)
- PDF Generation
