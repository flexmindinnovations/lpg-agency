# Phase 13: Cylinder Ledger Implementation Plan

## Goal
Implement the Cylinder Ledger bounded context to track exactly where every single cylinder is across the ecosystem. This serves as the double-entry tracking system for cylinder flow, tracks customer balances, and ties ledgers back to inventory balances for reconciliation.

## Scope
1. **Domain Layer**: `CylinderLedger` aggregate root, `LedgerTransaction` entity, `CylinderBalance` read model.
2. **Application Layer**: Use cases for recording deliveries (appended via Domain Events) and manually adjusting balances.
3. **Infrastructure Layer**: Repository for `CylinderLedger`, database schema migrations for ledger entries and balances with strict RLS tenant isolation.
4. **API Layer**: REST endpoints for fetching a customer's ledger, and exposing manual adjustment endpoint.
5. **Frontend UI**: `@lpg/ledger/feature-ledger` library to present the ledger data (transaction history, current balances, adjust action) as a standalone routed page (`/ledger/:customerId`).

## Integration points
- Listens to Domain Events like `CylinderDelivered` to append ledger transactions.
- Provides balance APIs to other bounded contexts for policy enforcement.

## Out of Scope
- Accounting & Billing (Phase 14)
