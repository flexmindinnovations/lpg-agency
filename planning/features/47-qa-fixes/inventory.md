# QA fixes: inventory, dispatch, fleet and compliance

Branch `qa-fix/inventory`. Paths below are relative to the repo root.

## Findings fixed

### DA-02: GRN Source OMC
- **Change:**
  - The API takes `source_omc` as a validated enum (`iocl` / `bpcl` / `hpcl` / `other`). Any case is accepted. An unknown value now returns 422; it used to cause a 500.
  - The dashboard field is now a select.
- **Files:**
  - `backend/src/lpg/domain/inventory/inventory_location.py` (`OMC_CODES`)
  - `backend/src/lpg/application/inventory/use_cases.py` (`_require_omc`)
  - `backend/src/lpg/api/v1/schemas/inventory.py` (`OmcCode`)
  - `frontend/libs/inventory/feature-inventory/...`
- **Verified by:**
  - unit test for OMC normalisation;
  - integration test (`test_inventory_count_approval.py`): a GRN with a bad OMC gets 422;
  - a jest test checks the GRN request body.

### DA-04: stock-count reconciliation
- **Rules now enforced:**
  - Recording a count no longer changes stock. The expected quantity is the book balance at the time of the count.
  - Approving applies the variance exactly once. Rows are locked during the decision, and a second approve returns 409 `RECONCILIATION_ALREADY_DECIDED`.
  - Maker-checker: the person who recorded a count cannot approve it (409 `SELF_APPROVAL_NOT_ALLOWED`).
  - Rejecting needs a reason and leaves stock unchanged.
  - The variance sign is kept on new rows: `from_status` is None for a gain and set for a loss.
- **New endpoints:**
  - `POST /reconciliation-records/{id}/reject`
  - `GET /inventory-locations/{type}/{ref}/reconciliation-records?state=`
- **Dashboard:**
  - A "Counts awaiting approval" list with Approve and Reject.
  - The Reconcile drawer no longer offers approval to the person who just counted.
- **Files:**
  - `backend/src/lpg/domain/inventory/reconciliation.py` (new)
  - `backend/src/lpg/domain/inventory/inventory_location.py` (`apply_count_variance`)
  - application use cases and ports
  - the SQLAlchemy reconciliation repository (`get_for_decision` takes a row lock)
  - the router
  - the migration
  - `feature-inventory`
- **Verified by:**
  - unit tests;
  - integration tests (`test_inventory_count_approval.py`): maker-checker, single approval, reject, cross-tenant 404;
  - `test_inventory_endpoints_smoke.py`, updated;
  - a jest test that the self-approval error is shown next to the count.

### DA-16: inventory drawer errors
- **Change:**
  - Each drawer shows its own error inside the drawer, once.
  - The error is cleared whenever a drawer opens.
  - The page-level "Done." banner is gone. Success is shown as a toast that names what was recorded (for example "GRN-… recorded").
  - Inventory mutations opt out of the global error toast with the new `SKIP_ERROR_TOAST` HttpContextToken.
- **Files:**
  - `frontend/libs/shared/data-access/src/lib/global-error-toast.interceptor.ts` (token)
  - `inventory.service.ts` (`inlineErrors()` on mutations)
  - `feature-inventory`
- **Verified by:**
  - interceptor spec: a request carrying the token is not toasted;
  - inventory spec: the error appears in the drawer, the page error stays null, there is no toast, and reopening clears it.

### DA-17: allowed status moves
- **Change:**
  - New `GET /inventory/status-transitions` endpoint, built from the domain tables (`status_change_targets()` / `adjustment_targets()`).
  - The Change Status and Adjust pickers show only "From" statuses that have a move, and only the "To" statuses allowed from the chosen "From".
  - "To" is reset when "From" changes.
  - An adjustment may also reverse a status move.
- **Verified by:**
  - domain unit tests;
  - integration test of the endpoint;
  - jest tests for the options and the reset.

### DA-18: balance grid
- **Change:** removed the fixed 260px height. The grid now sizes to its rows (`autoHeight`, page size 100), and the Quantity column is 140px wide.
- **Verified by:** dashboard build; visual check deferred to QA.

### DA-34: empties return, GRN documents, stock register
- **GRN:**
  - Takes `challan_number`, `invoice_number` and `truck_number`. They are stored, trimmed and upper-cased.
  - The dashboard drawer has the three new fields.
- **Empties return:**
  - `POST /warehouses/{id}/omc-returns` creates an `omc_return_note` with an `ERN…` number.
  - Allowed statuses: empty, damaged, leakage, quarantine.
  - Returns 409 when stock is short.
  - Dashboard: a "Return to OMC" drawer.
- **Stock register:**
  - `GET /inventory-locations/{type}/{ref}/stock-register?date_from&date_to`
  - Gives opening, receipts, issues and closing per cylinder type and status for each IST business day, up to 92 days.
  - Dashboard: a "Stock register" grid with a date range.
- **Verified by:** unit tests for the register walk-back and for return-to-OMC, plus integration tests.

### DO-23: one open trip per driver and van
- **Change:**
  - Planning a route, or assigning an order that creates one, refuses a driver or van that already has a planned, loaded or in-progress trip.
  - Errors: 409 `DRIVER_ALREADY_ON_TRIP` / `VEHICLE_ALREADY_ON_TRIP`.
  - Concurrent requests are serialised with advisory locks (`RouteRepository.lock_crew`).
- **Verified by:**
  - unit tests in `test_route_use_cases.py`;
  - `test_route_endpoints_smoke.py` step 13.

### DO-25: New trip branch and godown
- **Change:**
  - `/auth/me` now returns `branch_id`, and `AuthPrincipal.branchId` holds it.
  - New `AuthTokenStore.defaultBranchIdAmong(branches)`: returns the user's own branch if listed, else the only branch, else none.
  - New trip uses it. The godown defaults only to that branch's own warehouse, never another branch's.
  - The Branch selects in New trip, Register/Edit Driver and Register Vehicle have a placeholder and an `ariaLabel`. This fixes the collapsed empty bar and the axe `aria-input-field-name` error.
  - The orders hint reads "Choose a branch…" until a branch is chosen.
  - Dispatch has a public `reload()` for DO-24.
- **Verified by:**
  - `auth-token.store.spec.ts`;
  - auth smoke test asserts `branch_id`;
  - dashboard build.

### DO-32: cylinder retest due date
- **Change:**
  - `CylinderUnit` derives `test_due_date` when it is not given:
    - last test + 60 months; otherwise
    - manufacture date + 120 months, which is the first periodic test under Gas Cylinders Rules 2016 / IS 15975.
  - It exposes `test_due_basis` (`recorded` / `manufacture` / `unknown`).
  - The migration backfills never-tested units.
  - A unit past its due date is flagged by the existing due filter. The dashboard shows where the date came from and marks it overdue.
  - Blocking from fillable stock uses the existing rule: `ReceiveCylinderUnitUseCase` refuses to receive a unit that is due for test (409 `CylinderDueForStatutoryTestError`). Because the due date is now always computed, a never-tested old cylinder is blocked too, where before it slipped through.
- **Verified by:**
  - `tests/unit/test_cylinder_unit.py::TestStatutoryDueDateFromManufacture`;
  - updated integration suggestion tests;
  - cylinder-units jest tests.

### DO-33: Compliance Calendar
- **Change:**
  - `GET /compliance-documents?expiry=upcoming` returns documents that are overdue or due within 90 days, across all owners, earliest first.
  - The page now leads with an "Upcoming expiries" grid:
    - covers warehouse Form F, agency insurance, driver licences and vehicle papers;
    - columns: status chip (overdue / due soon / upcoming), days left, owner name.
  - "Tenant — Insurance Policy" is now "Agency insurance".
  - `lpg-compliance-documents-panel` takes a new `heading` input. The calendar passes `null`, so the "Compliance Documents" sub-heading no longer repeats (UR-02).
- **Verified by:**
  - compliance smoke integration test (overdue before soon, far-off excluded);
  - calendar jest tests.

### DO-34: driver name, phone and licence warning
- **Change:**
  - `DriverResponse` gains `name` and `phone_number`. They are resolved in one query through `DriverRepository.contacts_for_employees`.
  - The driver drawer shows name and phone (as a `tel:` link) and tags a licence that is expired, expiring or missing a date.
  - The list has a Licence chip column and a warning banner counting expired and expiring licences.
- **Verified by:**
  - driver smoke integration test (get and list);
  - drivers jest tests (`licenceState`, warning counts, name preference).

### DR-04: van load manifest
- **Change:** the manifest is the whole van: free filled stock plus what is still reserved for orders on the trip. A top-up replaces the manifest and clears the driver's confirmation only when the totals change.
- **Verified by:** `test_load_and_dispatch_route.py` (2 on van + 1 loaded = 3; top-up; confirmation kept).

### DR-13: order numbers on route stops
- **Change:** `Route.assign_order(..., order_number=...)` is now set in both the plan path and the assign path, so a stop's `order_number` is never null for new stops.
- **Verified by:** unit test; stops carry `ORD000006`.

### DR-05 (backend)
- **Change:** `get_active_route_for_driver` prefers in-progress, then loaded, then planned, then the newest.
- **Verified by:** route tests.

## Migration
- **Revision `9aee17794c55`** (down_revision `c8d4e2f6a1b3`):
  - adds the GRN document columns;
  - adds `omc_return` to the transaction type check;
  - creates `omc_return_note`, with RLS and grants;
  - adds the reconciliation reject columns and a single-decision check;
  - closes old pending counts as rejected, because their stock had already been applied under the old flow;
  - backfills `test_due_date` from manufacture date + 10 years.
- **Verified:** upgrade, downgrade and upgrade again on `lpg_test_inventory`.

## API changes (client regenerated in two `chore(api): regenerate client` commits)
- **New endpoints:**
  - `GET /inventory/status-transitions`
  - `GET /inventory-locations/{type}/{ref}/stock-register`
  - `GET /inventory-locations/{type}/{ref}/reconciliation-records`
  - `POST /reconciliation-records/{id}/reject`
  - `POST /warehouses/{id}/omc-returns`
- **Changed endpoints:**
  - GRN request and response: challan, invoice and truck numbers; `source_omc` is an enum.
  - Reconciliation response: `state`, `recorded_at`, and the reject fields.
  - Status-change, adjust and reconcile requests type `status` as a `CylinderStatus` literal.
  - `DriverResponse`: `name`, `phone_number`.
  - `PrincipalResponse`: `branch_id`.
  - Cylinder unit: register accepts `last_tested_at` / `test_due_date`; the response has `test_due_basis`.
  - `RouteStop.order_number` is filled.
  - `GET /compliance-documents` accepts `expiry=upcoming`.
- **Behaviour changes:**
  - Approving a count changes stock; recording a count does not.
  - Self-approval returns 409.
  - A second open trip for the same driver or van returns 409.

## Test results
- **Backend** (`lpg_test_inventory`, with a URL-redirect plugin for tests that hardcode `lpg_test`): 1755 passed, 6 failed.
  - The 6 failures are the known baseline: `test_database` ×2 and `test_employee_endpoints_smoke` ×3.
  - Plus `test_settings` migration-url ×1, which fails only because my env exports `LPG_MIGRATION_DATABASE_URL`.
- **Backend checks:** ruff, ruff format, `mypy --strict` and import-linter (7 contracts) are all clean.
- **Frontend:** `nx test` and `nx lint` are green for:
  - shared-data-access
  - shared-ui
  - inventory-feature-inventory
  - feature-dispatch
  - delivery-feature-drivers
  - delivery-feature-vehicles
  - compliance-feature-compliance-calendar
  - compliance-feature-cylinder-units
  - dashboard
- **Dashboard build:** `nx build dashboard` succeeds.

## Deferred
- **Driver drawer:** current trip, vehicle and cash to settle (DO-34 "expected" extras) are not shown. That needs route and cash queries per driver and belongs with the cash-handover work.
- **Cylinder Units registration form:** does not yet show the new `last_tested_at` / `test_due_date` inputs. The API accepts them and derives the date when they are omitted, which covers the finding.
- **Compliance Calendar:** does not yet include scale certificates or cylinder retests. They have their own pages with due filters.
- **Stock register:** reconstructs history from the transaction ledger. Rows written before the reconciliation sign change (a loss whose `from_status` is null) show as gains in the register for old dates. Current balances are unaffected.
- **Uniqueness:** there is no database unique index for "one open trip per driver/van", because existing data may already hold duplicates. The rule is enforced in the application under advisory locks.
- **Register Driver leak:** `openRegisterModal` subscribes to `branch_id.valueChanges` on every open, so subscriptions pile up. This was seen but not fixed (out of scope).

## Notes for the lead (merge)
- **Shared files touched:**
  - `global-error-toast.interceptor.ts` (new `SKIP_ERROR_TOAST` token, additive)
  - `auth-token.store.ts` / `auth.service.ts` (`branchId`, `defaultBranchIdAmong`)
  - `auth.py` `/me` and `PrincipalResponse` (`branch_id`)
  - `compliance-documents-panel` (`heading` input)
  - These may meet the identity, realtime and UI engineers' changes. All are additive.
- **Regenerated client:** the two `chore(api)` commits only contain my schema changes. If other branches also regenerate, rerun the generator after merging rather than hand-merging generated files.
- **Semantic change:** `loaded_lines` / the van manifest now means "full van", not "this load only". The driver app shows the manifest as is.
- **Shared scratchpad incident:** early on, the shared scratchpad `env.sh` was overwritten by another session, and one `alembic upgrade` of mine ran against `lpg_test_orders`. That database has since been reset (checked: no `omc_return_note`, alembic at `7bc2ddcd8ed9`). Since then I have used only `/tmp/claude-0/inventory-work/env.sh` (`lpg_test_inventory`, Redis db 5).
- **Dispatch refresh:** dispatch exposes `reload()` for DO-24, and the inventory page has `reload()` as well.

## ADR draft
**Stock-count reconciliation is two-person and applies on approval.**

- **Context:**
  - A count used to change stock as soon as it was recorded. Approving then applied it again.
  - Anyone, including the counter, could approve.
- **Decision:**
  - A count records the book quantity and the variance only.
  - A different user with `reconciliation:approve` approves it. Approval applies the variance exactly once, under a row lock.
  - The count can instead be rejected with a reason.
  - The single-decision rule is backed by a check constraint.
  - Old pending counts are closed as rejected by the migration, because their stock had already been applied.
- **Consequences:**
  - Book stock stays wrong until a count is approved.
  - The dashboard surfaces pending counts on the location page.
  - The variance sign is now recoverable from the ledger.
