# Phase 13: Cylinder Ledger Implementation Plan

## Goal
Implement the Cylinder Ledger bounded context to track exactly where every single cylinder is across the ecosystem. This serves as the double-entry tracking system for cylinder flow (Warehouse → Vehicle → Customer), tracks customer balances, and ties ledgers back to inventory balances for reconciliation.

## Scope
1. **Domain Layer**: `CylinderLedger` aggregate root, `LedgerTransaction` entity, `CylinderBalance`, `LedgerTransactionType` value objects.
2. **Application Layer**: Use cases for recording transfers, updating customer balances, and producing a reconciliation statement.
3. **Infrastructure Layer**: Repository for `CylinderLedger`, database schema migrations for ledger entries and balances.
4. **API Layer**: REST endpoints for fetching a customer's ledger, and exposing system-wide discrepancies.
5. **Frontend UI**: `@lpg/ledger/feature-ledger` library to present the ledger data (transaction history, current balances).

## Integration points
- Listens to Domain Events like `OrderDelivered`, `OrderCollected`, `RouteReconciled` to append ledger transactions.
- Provides balance APIs to Order Management for Cylinder Cap Policy enforcement.

## Out of Scope
- Accounting & Billing (Phase 14)
