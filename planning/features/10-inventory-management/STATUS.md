# Phase 10 — Inventory Management Status

## Status: ✅ COMPLETE

**Started:** 2026-08-11
**Completed:** 2026-08-11

---

## Progress

| Area | Status |
|---|---|
| Planning docs | ✅ Done |
| Database migration | ✅ Done (`4f8b2d6a9c1e_create_inventory_schema.py`) |
| Domain layer | ✅ Done (`inventory_location.py`) |
| Application layer | ✅ Done (`ports.py`, `use_cases.py`) |
| Infrastructure layer | ✅ Done (`models/inventory.py`, `repositories/inventory.py`) |
| API layer | ✅ Done (`schemas/inventory.py`, `dependencies/inventory.py`, `routers/inventory.py`, mounted in `app.py`) |
| Backend tests | ✅ Done (34 domain unit + 11 use-case unit + 11 endpoint/RBAC/projection integration = 56 new tests; 511 total backend tests passing) |
| OpenAPI regeneration | ✅ Done (`openapi.json` exported and verified with `--check`, Angular client regenerated) |
| Frontend UI | ✅ Done (`libs/inventory/feature-inventory`, route & nav link wired) |
| Frontend tests + build | ✅ Done (`inventory-feature-inventory` lint/test/build clean) |
| Quality Gates | ✅ Done (`mypy --strict`, `import-linter` 5/5, `ruff check`, `ruff format` all clean on touched code) |
| Live browser verification | ✅ Done |
| Documentation | ✅ Done |

---

## Verification Summary

- **Backend tests:** 511 passed (56 new: 34 domain unit, 11 use-case unit,
  11 integration — endpoint smoke lifecycle, RBAC incl. live-recheck for
  `reconciliation:approve`, balance/transaction lockstep + cross-tenant RLS
  isolation).
- **Backend architecture:** `mypy --strict` 0 errors across 144 files,
  `import-linter` 5/5 contracts kept, `ruff check`/`format --check` clean
  across the whole backend.
- **Frontend:** `inventory-feature-inventory` lint/test/build all pass.
- **Live browser verification** (against a real local Postgres + FastAPI +
  Angular dev server, logged in as `agency_admin`):
  1. Balance on a never-touched warehouse → all-zero, no error.
  2. Goods receipt of 50× 14.2kg cylinders → Filled balance = 50,
     `grn_receipt` transaction recorded.
  3. Load transfer of 1 unit warehouse→vehicle → warehouse Filled 49,
     vehicle Filled 1, `unload`/`load` transactions recorded on each side.
  4. Status change filled→leakage (valid edge) → balance updates
     correctly (Filled 49→48 warehouse-side action; vehicle: 1 delivered).
  5. Status change filled→empty (invalid edge) → `409
     INVALID_STATUS_TRANSITION`, friendly UI message, balance unchanged.
  6. Delivery of 1 unit from the vehicle → vehicle Filled 1→0, `delivery`
     transaction recorded.

---

## Bugs found and fixed during implementation

Independent verification (real DB, not just self-reported gate status)
surfaced several real defects, all fixed before close-out:

- **Migration double-seeded already-existing permission data.** Phase 6's
  `fa52b77ec442` had already seeded `inventory:load`/`inventory:adjust`/
  `reconciliation:approve` as permission codes, with `inventory:adjust`
  and `reconciliation:approve` already carrying grants matching
  `docs/data/17-api-security.md` §6 exactly. The first migration draft
  tried to re-insert all four permission codes and their full grant
  matrices, which would have violated `uq_identity_permission_code` (and,
  had it used `INSERT ... SELECT` instead, would have silently
  double-granted). Fixed: only `inventory:read` is a new permission code;
  role grants are resolved by joining on `permission.code` (works whether
  the row pre-existed or was just inserted) with `ON CONFLICT DO NOTHING`,
  and the migration's `downgrade()` only removes what it added.
- **`InventoryLocationRepository.save()` produced a duplicate-row /
  foreign-key-ordering bug** when two pending transactions in one `save()`
  call touched the same `(cylinder_type, status)` balance key (e.g.
  `receive_goods` then `unload` before the first save), or when a brand
  new location's dependent rows were flushed in the same batch as the
  parent row. Fixed with an in-call balance-row cache (avoids the
  duplicate-insert) and explicit `flush()` calls after inserting a new
  location/transaction row so FK-dependent rows are never batched ahead of
  the row they reference — confirmed via a real-database smoke run before
  the automated test suite existed to catch it.
- **`ReconciliationRecordModel.variance` (a DB `GENERATED ALWAYS AS ...
  STORED` column) wasn't marked `Computed()` in the SQLAlchemy model**,
  so the ORM tried to `INSERT`/read it like a normal column — the INSERT
  path happened to work (RETURNING captures it), but `approve()`'s
  UPDATE path crashed with `MissingGreenlet` when reading the
  now-expired attribute outside an explicit refresh. Fixed by declaring
  `Computed()` on the model column and calling `session.refresh()` after
  the UPDATE, before building the response.
- **The local dev database was several migrations behind** (`lpg_dev` sat
  at an old revision) and the running `backend-dev` uvicorn process had no
  `--reload` flag, so it kept serving 404s for the new router after the
  migration and code were both in place — required an explicit server
  restart mid-verification, not a code defect but worth noting for anyone
  re-running this phase's verification steps.

---

## Pre-existing issues found, not fixed (out of scope for this phase)

`npx nx run-many -t lint test build` surfaced failures in projects this
phase never touched — confirmed via `git diff --stat` to be substantial
(700+ line) uncommitted changes from the prior "admin pages card wrapper +
success feedback" pass, not caused by Inventory Management. Flagged as a
separate follow-up task rather than fixed here:

- `customer-feature-customers:lint`/`:test` — an empty `<button>` and a
  failing Jest assertion in `feature-customers.html`/`.ts`.
- `admin-feature-tenant-settings:lint`, `admin-feature-audit-log:lint`.
- `dashboard:test` — `shell-layout.spec.ts` fails on every test with
  `NG0201: No provider found for _MessageService` (PrimeNG `<p-toast>`
  needs `MessageService`, provided in the real `app.config.ts` but missing
  from the spec's `TestBed` providers). Confirmed this is test-config-only
  — the real running app provides `MessageService` and the app renders
  correctly in the browser.

A second, earlier-discovered and separately-flagged issue (not part of
this phase, found while confirming the correct `DomainError`-handling
pattern to follow): `delivery.py`'s router manually catches `DomainError`
and downgrades it to a generic `422` with no `error_code`, silently
overriding the global RFC 7807 handler's correct `409` + `error_code`
mapping. `inventory.py`'s router deliberately does **not** repeat this —
domain and application errors propagate untouched to the global handler.

---

## Documentation corrections made as part of this phase

- `docs/data/11-api-contracts.md` line 143's parenthetical inconsistently
  called `inventory:adjust` "live-checked"; `docs/data/17-api-security.md`
  §7's authoritative list (and `require_live_permission`'s own docstring)
  names exactly 4 live-checked actions, none of which is
  `inventory:adjust`. Corrected the parenthetical rather than expanding
  live-check scope unasked.
