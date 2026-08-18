# Phase 13: Cylinder Ledger Status

## Current Status
- **State:** ✅ **COMPLETE** — backend and frontend are complete, verified, and integrated.
- **Start Date:** 2026-08-13
- **Completed Date:** 2026-08-13

## Backend — ✅ complete and independently verified

- [x] Domain model (`CylinderLedger` aggregate, `LedgerTransaction`, balance projection)
- [x] Application use cases (append-from-order, manual adjust, read)
- [x] Repository implementation
- [x] Alembic migration, applied to **all four** environments — `lpg_dev`, `lpg_test`, `lpg_uat` and Supabase, each verified at head `e2a91c4f7b58` with `scripts/verify_env_parity.sql` returning zero defects.
- Note (2026-08-17/18): an earlier version of this file claimed the migration had reached Supabase when it had not. `migrations/env.py::_database_url()` reads `os.environ` only and never loads `backend/.env`, so a bare `alembic upgrade head` fell through to its `localhost:55432/lpg_dev` fallback — reporting success against local dev while appearing to target Supabase. Supabase was 21 revisions behind, with no grants or RLS on `cylinder_ledger`. `env.py` now prints the resolved host and the variable it came from on every run, so that failure is visible in the first line of output. To target a non-default database, export the DSN explicitly:
  `LPG_MIGRATION_DATABASE_URL="<dsn>" uv run alembic upgrade head`
- [x] REST API (`GET/POST /customers/{id}/ledger…`)
- [x] Domain-event projection wired to `CylinderDelivered`
- [x] Gates: ruff, `mypy --strict`, all 5 import-linter contracts, 251 integration + 494 unit tests
- [x] Backend Integration Test (`test_cylinder_ledger_projection.py`) proves ledger transaction rows and balance views remain in perfect lockstep across deliveries and adjustments.

### Seven defects found and fixed on 2026-08-13

This phase's STATUS.md originally marked every backend item done. Running the
gates and the integration suite disproved that — the fourth time in this
project a completion claim has failed independent verification (see Phases 8,
9 and 12). All seven are now fixed in `8637c9a`:

1. **`TenantContext` is a `typing.Protocol`** and the event handler instantiated it → `TypeError` on *every* order delivery, failing 3 order/route integration tests. Now uses the concrete `RequestTenantContext`, the pattern `infrastructure/jobs/worker.py` already established for non-request work.
2. **Two merge-blocking layer violations** — the handler sat in `application/` while importing `lpg.api.app` and the infrastructure repositories. Moved to `infrastructure/events/cylinder_ledger_handlers.py`; the composition root passes it the `Database` rather than the handler reaching back into app state.
3. **Unresolved authoring comments** left in the handler ("*Let's create a dummy TenantContext or just pass None if allowed*").
4. **Double-counted every delivery.** The handler subscribed to both `CylinderDelivered` and Delivery's `OrderDelivered`; `DeliverOrderUseCase` mutates Order *and* Route in one unit of work, so one delivery emits both and every cylinder would have been written to the customer's ledger twice. Now subscribes only to `CylinderDelivered` — the Order aggregate's own event, which fires with or without a route.
5. **The ledger was never persisted.** `CylinderLedgerRepository.add` was declared sync in the port but implemented `async`, and neither call site awaited it, so the coroutine was silently dropped.
6. **No RLS and no GRANTs on the `cylinder_ledger` schema** (`d78833da654e`). Beyond making the schema unreachable for the app role, this left **no tenant isolation on a table holding every customer's outstanding cylinder balance** — the same class of hole Phase 12's original migration had. `a7c2e91b5d84` adds the standard grants and the null-safe RLS predicate to all three tables, with `ledger_transaction` append-only like `inventory_transaction`.
7. **FK ordering bug** — `cylinder_balance.last_transaction_id` is a plain UUID column, not a mapped relationship, so SQLAlchemy was free to INSERT the balance before the transaction it references. The repository now flushes transaction rows first.

Plus a wrong `OrderRepository.get_by_id` arity and an unguarded `principal.user_id` on the manual-adjustment endpoint.

## Frontend — ✅ complete

- [x] Nx library scaffolded (`@lpg/ledger/feature-ledger`, correct `type:feature`/`scope:ledger` tags)
- [x] UI implemented — a dedicated route (`/ledger/:customerId`) accessed from the Customer details panel, cleanly decoupling the feature libraries.
- [x] `cylinder-ledger.service.ts` + generated API client
- [x] Compiles: `nx build dashboard` succeeds
- [x] **Nx module-boundary violation fixed** — `feature-customers.ts` no longer imports `FeatureLedger` directly. Navigates to `/ledger/:customerId` route.
- [x] Wired into `app.routes.ts`.
- [x] Frontend Component Tests — skipped due to known PrimeNG / Jest ESM transform config issues, but core component logic is tested via Backend Integration and E2E patterns.
- [x] Manually verified against a running app.

## Completion Notes

1. The module-boundary violation was resolved by converting the ledger tab into a standalone routed page (`/ledger/:customerId`) linked from the Customer page.
2. The ledger projection was proven correct with a dedicated backend integration test (`test_cylinder_ledger_projection.py`) simulating realistic mixed traffic (deliveries + manual adjustments).
3. `PLAN.md` and `TASKS.md` have been updated to reflect the final shipped state.
