# Phase 13: Cylinder Ledger Status

## Current Status
- **State:** 🟡 **IN PROGRESS** — backend complete and green; frontend renders but has one architectural violation and has never been verified against a running app.
- **Start Date:** 2026-08-13
- **Completed Date:** — (not yet complete)

## Backend — ✅ complete and independently verified

- [x] Domain model (`CylinderLedger` aggregate, `LedgerTransaction`, balance projection)
- [x] Application use cases (append-from-order, manual adjust, read)
- [x] Repository implementation
- [x] Alembic migration, applied to the local test DB **and** the Supabase dev DB
- [x] REST API (`GET/POST /customers/{id}/ledger…`)
- [x] Domain-event projection wired to `CylinderDelivered`
- [x] Gates: ruff, `mypy --strict`, all 5 import-linter contracts, 251 integration + 494 unit tests

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

## Frontend — 🟡 partial

- [x] Nx library scaffolded (`@lpg/ledger/feature-ledger`, correct `type:feature`/`scope:ledger` tags)
- [x] UI implemented — a "Cylinder Ledger" tab on the Customer detail panel (`feature-customers.html`), ~294 lines of component + template
- [x] `cylinder-ledger.service.ts` + generated API client
- [x] Compiles: `nx build dashboard` succeeds
- [ ] **Nx module-boundary violation (blocking `lint`)** — `feature-customers.ts` imports `FeatureLedger` directly, and a `type:feature` library may not depend on another `type:feature` library. `customer-feature-customers:lint` fails on this today. Needs a real decision, not a tag edit: either extract the ledger panel into a `type:ui` library, or give the ledger its own route instead of embedding it in Customer detail.
- [ ] Not wired into `app.routes.ts` or the sidebar nav — it is reachable *only* as a tab inside Customer detail
- [ ] No component tests
- [ ] **Never manually verified** against a running app

## Pending to close this phase

1. Resolve the module-boundary violation (see above) so `nx lint` passes.
2. Decide whether the ledger deserves its own route/nav entry alongside the customer-detail tab.
3. Backend tests exist only as `test_domain_cylinder_ledger.py` (unit). No use-case tests for the event projection, and no integration test asserting a delivery actually lands ledger rows — the projection is currently only exercised *indirectly*, via the order/route lifecycle tests that were failing because of it.
4. Live browser verification of the ledger tab.
5. Phase documentation: `PLAN.md`/`TASKS.md` in this folder still describe the original intent rather than what was built.
