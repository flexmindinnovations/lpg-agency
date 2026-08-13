# Phase 10 — Inventory Management Tasks

- [x] Step 1: Planning docs
  - [x] Create PLAN.md
  - [x] Create TASKS.md (this file)
  - [x] Create STATUS.md

- [x] Step 2: Database Migration
  - [x] Create Alembic migration: `inventory` schema, 5 tables, RLS,
        `inventory:read` permission + role grants for `inventory:load`

- [x] Step 3: Domain Layer
  - [x] domain/inventory/__init__.py
  - [x] domain/inventory/inventory_location.py (`InventoryLocation`
        aggregate, `InsufficientStockError`/`InvalidStatusTransitionError`,
        `GoodsReceived`/`InventoryAdjusted` events)

- [x] Step 4: Application Layer
  - [x] application/inventory/__init__.py
  - [x] application/inventory/ports.py (repository protocols + read-model
        dataclasses)
  - [x] application/inventory/use_cases.py (lazy create-on-first-use
        throughout)

- [x] Step 5: Infrastructure Layer
  - [x] infrastructure/persistence/models/inventory.py (5 ORM models,
        `Computed()` on the generated `variance` column)
  - [x] Register models in Base metadata
  - [x] infrastructure/persistence/repositories/inventory.py (balance
        projection kept in lockstep with the transaction ledger)

- [x] Step 6: API Layer
  - [x] api/v1/schemas/inventory.py
  - [x] api/v1/dependencies/inventory.py
  - [x] api/v1/routers/inventory.py (10 endpoints; no manual `DomainError`
        catching — propagates to the global RFC 7807 handler)
  - [x] Mount inventory router in app.py

- [x] Step 7: Tests — Backend
  - [x] tests/unit/test_domain_inventory_location.py
  - [x] tests/unit/test_inventory_use_cases.py
  - [x] tests/integration/test_inventory_endpoints_smoke.py
  - [x] tests/integration/test_inventory_rbac.py (incl. live-recheck class
        for `reconciliation:approve`)
  - [x] tests/integration/test_inventory_balance_projection.py (lockstep +
        cross-tenant RLS isolation)

- [x] Step 8: Backend Quality Gates
  - [x] pytest passes (511 tests)
  - [x] ruff check/format passes
  - [x] mypy --strict passes
  - [x] import-linter passes (5/5 contracts)

- [x] Step 9: OpenAPI Regeneration
  - [x] export_openapi.py
  - [x] ng-openapi-gen regenerates Angular client

- [x] Step 10: Frontend
  - [x] Create libs/inventory/ Nx library group
  - [x] inventory.service.ts data-access wrapper
  - [x] feature-inventory: location picker + balance grid + transaction
        history + 6 action drawers
  - [x] Wire route in app.routes.ts
  - [x] Add sidebar nav link in ShellLayout

- [x] Step 11: Frontend Quality Gates
  - [x] nx lint/test inventory-feature-inventory passes
  - [x] nx run-many -t lint test build — inventory projects clean (see
        STATUS.md for pre-existing, unrelated failures found and flagged
        separately)

- [x] Step 12: Live Browser Verification
  - [x] Balance on a never-touched warehouse → all-zero, not an error
  - [x] Goods receipt credits Filled
  - [x] Load transfer moves stock warehouse→vehicle atomically
  - [x] Delivery decrements vehicle Filled independently of Collection
  - [x] Valid status transition (filled→leakage) succeeds
  - [x] Invalid status transition (filled→empty) → 409, friendly UI message
  - [x] Transaction history reflects every mutation in order

- [x] Step 13: Documentation
  - [x] Update STATUS.md
  - [x] Update planning/current_phase.md
  - [x] Update knowledge/12-current-status.md
  - [x] Correct `docs/data/11-api-contracts.md` line 143's inconsistent
        "live-checked" parenthetical on `inventory:adjust`
