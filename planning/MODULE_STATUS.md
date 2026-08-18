# Module Status — Verified Baseline

**Generated:** 2026-08-18 · **Last updated:** after R13 · **Migrations:** `f3c8a56d29e1` (local `lpg_dev`/`lpg_test`/`lpg_uat`; Supabase not yet migrated)

## How this was produced

Every row was checked by running the project's own CI commands and reading the
code — not by reading `STATUS.md` files. Where a doc claim and the measured
result disagree, the measured result wins and the disagreement is recorded.

| CI command | Result |
|---|---|
| `uv run ruff check .` | **524 errors** (was 634; 109 of the drop is `backend/scratch/` now gitignored, 1 from R1 — not a code-quality improvement) |
| `uv run mypy` | **18 errors in 6 files** (was 23 in 10) |
| `uv run lint-imports` | **2 of 5 contracts BROKEN** |
| `uv run pytest tests/unit` | 514 passed |
| `uv run pytest tests/integration` | **0 failed**, 253 passed (was 18 failed / 234 passed originally) |
| `npx nx run-many -t lint` | **7 of 24 projects fail** |
| `npx nx run-many -t test` | **4 of 23 projects fail** |
| `npx nx build dashboard` | succeeds |

This file exists because four separate phases were marked COMPLETE in their own
`STATUS.md` and then failed independent verification (Phases 8, 9, 12, 13). The
table below is the corrective: one place where "complete" means *the gates
pass*, not *someone said so*.

## Legend

| Mark | Meaning |
|---|---|
| ✅ | Verified — code present **and** its gates pass |
| 🟡 | Functionality present and building, but a gate it owns is red |
| 🔴 | Materially incomplete, untested, or unverifiable |
| ⚪ | Foundation phase, no user-facing surface |

**Impl** = shipped functionality. **Verified** = that functionality with green
gates. A module can be 100% implemented and 0% verified; that gap is the
backlog this file tracks.

## Master table

| # | Module | Docs claim | Verified actual | Impl | Verified | Gate failures owned | Missing / blocking |
|---|---|---|---|---|---|---|---|
| 00 | Documentation baseline | complete | ⚪ exists, partly stale | 100% | n/a | — | Phase 13 + `current_phase` claims corrected 2026-08-18; no planning dirs for 11/16/17 |
| 01 | Repository foundation | complete | ⚪ ✅ | 100% | ✅ | — | — |
| 02 | Backend foundation | complete | ⚪ 🟡 | 100% | 🟡 | ruff: `infra/persistence` 55, `infra/jobs` 43 | Lint debt only; no functional gap |
| 03 | Shared infrastructure | complete | ⚪ 🟡 | 100% | 🟡 | import-linter: `realtime/connection_manager` → fastapi | Import is type-only under `TYPE_CHECKING`; needs `ignore_imports` entry **or** refactor — decision required |
| 04 | Angular web foundation | complete | ⚪ ✅ | 100% | ✅ | — | — |
| 05 | Flutter foundations | complete | ⚪ ❓ | 100% | ❓ | not exercised | 12 dart tests exist; mobile CI **not run** in this pass — unverified, not assumed broken |
| 06 | Auth & authorization | complete | ✅ | 100% | ✅ | import-linter `routers/auth.py` → sqlalchemy (C2, open) | C9 fixed in R11 — new users now get their role's permissions on creation |
| 07 | Admin / tenant master data | complete | 🟡 backend ✅ | 100% | 🟡 | lint: `admin-feature-flags`, `admin-feature-tenant-settings` | Backend gap closed by R13; frontend lint errors remain |
| 08 | Customer management | ✅ COMPLETE | ✅ | 100% | ✅ | — | C1 fixed in R1; stale KYC test key fixed in R11 pass |
| 09 | Driver management | ✅ COMPLETE | ✅ | 100% | ✅ | — | — |
| 10 | Inventory management | ✅ COMPLETE | ✅ | 100% | ✅ | — | Was C10 (exception-swallowing), fixed |
| 11 | Order management | complete (no planning dir) | ✅ | 100% | ✅ | — | All 8 original failures cleared (C1, C9, C10 combined). `planning/features/11-order-management/` still **does not exist** |
| 12 | Delivery & dispatch | ✅ COMPLETE "verified independently" | ✅ | 100% | ✅ | — | Was C10, fixed |
| 13 | Cylinder ledger | ✅ COMPLETE | ✅ backend + frontend | 100% | ✅ | — | Route `/ledger/:customerId` **confirmed wired** (`app.routes.ts:50`); 7 defects fixed 2026-08-13 |
| 14 | Accounting / invoicing | ✅ COMPLETE | 🔴 untested | ~90% | 🔴 | lint: `feature-invoices` (2 **blank buttons**) | **No invoice endpoint tests, no accounting integration tests.** See C3 |
| 15 | Notifications | Backend COMPLETE | 🟡 tested, gates red | 100% | 🔴 | lint + test: `notification-feature-notifications` | Frontend lint and unit tests failing |
| 17 | Complaint management | ✅ COMPLETE (in `current_phase`) | 🔴 **zero backend tests** | ~90% | 🔴 | test: `feature-complaints`; import-linter `routers/complaint.py` → sqlalchemy; ruff `domain/complaint` 27 | Full aggregate + router with **no tests at all**; 2 blank buttons; no planning dir |
| 18 | Printing engine | ✅ COMPLETE | 🟡 partial tests | 100% | 🟡 | ruff: `application/printing` 4 | Unit test only; no integration test |
| 19 | Customer app V2 | In Progress | 🔴 in progress | ~35% | 🔴 | — | 16 dart files in `customer_app` — the **only module whose doc status is honest** |
| — | Reporting | folded into 18 | 🔴 **router never mounted — 100% dead** | ~90% built, **0% reachable** | 🔴 | lint: `reporting-feature-reports`; ruff `application/reporting` 26 | See C7 — every endpoint 404s |
| — | Employees (tenant-admin) | — | 🔴 **zero tests** | ~90% | 🔴 | lint: `feature-employees` | No tests — this is the table whose missing GRANT caused the `permission denied` outage |
| — | Dashboard shell | — | 🟡 builds, tests red | 100% | 🔴 | lint + test: `dashboard` | `shell-layout.ts` statically imports 2 lazy libs → breaks lazy boundary **and** `shell-layout.spec.ts` |
| — | Shared data-access | — | 🟡 | 100% | 🔴 | test: `shared-data-access` | Unit tests failing |
| 20 | Regulatory & MDG Compliance | *(new)* | 🔵 planned | 0% | — | — | Hard requirements — weighment, TDT rating, cylinder identity, DAC, vouchers, PAHAL/PMUY, compliance calendar, cash settlement |
| 21 | AI Foundation | *(new)* | 🔵 planned | 0% | — | — | Model gateway, feature store, evaluation harness, guardrails, kill switch |
| 22 | AI Operational Intelligence | *(new)* | 🔵 planned | 0% | — | — | Classical ML — refill prediction, demand forecast, routing, anomaly detection, credit, churn, ETA |
| 23 | AI Assistive Interfaces | *(new)* | 🔵 planned | 0% | — | — | LLM/hybrid — complaint triage, KYC extraction, conversational ordering, voice, analytics copilot, MDG copilot |

## Cross-cutting issues

Not owned by one module — fix once, centrally.

### C1 — `address_line` → `line_1` drift ✅ RESOLVED (R1, 2026-08-18)

Migration `de17b27d462e` restructured `customer.customer_address` into
`line_1`/`line_2`/`area`/`city`/`district`/`state`/`pincode`. Product code is
**correct**; only `tests/` still writes the removed `address_line` column.

Verified that `DeliveryAddress.address_line` (Order aggregate snapshot VO) and
`tenant.warehouse.address_line` are legitimately different fields — **do not
rename those.**

Files: `test_order_endpoints_smoke.py:264`, `test_route_endpoints_smoke.py:413`,
`test_customer_repository.py:108`, `test_customer_endpoints_smoke.py:162`.

**Fixed 2026-08-18 (R1).** Cleared 11 of 18 failures — 8 from the fixture
rename plus 3 more from adjacent stale test code (`_seed_user` called with a
positional email, an undefined `role` variable). The prediction that it would
clear all 18 was wrong: the remaining 7 turned out to be C9, a real product
regression that this fix uncovered.

**Second pass — the frontend had drifted too, and the first pass missed it.**
R1 was initially scoped to `backend/tests/` only, on the assumption the rename
was contained there. Sweeping `frontend/` and `mobile/` found two more:

| Site | Defect |
|---|---|
| `order-queue.html:81` | `optionLabel="address_line"` bound over `customer.addresses`. `CustomerAddressResponse` carries `line_1` and has no `address_line`, so **every option in the Create Order "Delivery Address" dropdown rendered blank** — user-visible, and nothing failed loudly. Now `line_1`. |
| `customer-onboarding-wizard.component.ts:160` | Sent `address_line` inside a `RegisterCustomerRequest`. That schema has had `line_1`/`area`/`city`/… since `de17b27d462e` and no `address_line`; Pydantic's default `extra="ignore"` dropped it silently. The step *looked* like it registered an address and never did — the address was only ever created by the `addAddress` call that follows. Removed, with the reason recorded in place. |

Checked and correct, left alone: `tenant.warehouse.address_line` (a real
column), the Order aggregate's `DeliveryAddress.address_line` (a snapshot value
object) in `order-detail.html`, `feature-dispatch.html` and the mobile
`DeliveryAddressPayload`, and mobile's `CustomerAddressResponse` which already
reads `line_1`. Four of the six frontend hits were false alarms — the two real
ones only surface by checking each against the generated model.

**Follow-up, not fixed (R12):** the onboarding wizard collects structured
address fields and then flattens all eight into a single `line_1` string before
calling `addAddress`, which accepts only one line. That discards exactly the
structure `de17b27d462e` was written to introduce, and defeats any future
routing or pincode-based feature. Fixing it means widening the
`CustomerService.addAddress` signature.

### C2 — Clean Architecture contracts (2 of 5 broken)

- `lpg.api` → `sqlalchemy`: `routers/auth.py:29` (uncommitted), `routers/complaint.py:5-6`, several `dependencies/*`. Raw `text()` executed from the API layer.
- `lpg.infrastructure` → `fastapi`: `realtime/connection_manager.py:21` — **type-only, under `TYPE_CHECKING`**. Judgement call: add `ignore_imports` or invert the dependency. No runtime coupling exists.

### C3 — PrimeNG v22 blank buttons (user-visible)

`<button pButton icon="…" label="…">` — both attributes are **no-ops on the
directive**; they exist only on the `<p-button>` *component*. These render
**empty**. Correct pattern is `<i pButtonIcon>` + `<span pButtonLabel>`; the
label span is required, or `ButtonDirective.isIconOnly` collapses the button.

Remaining: `feature-invoices.html:114,122`, `feature-complaints.html`.

### C4 — Zero test coverage on four shipped modules

`complaint`, `reporting`, `employee`, `invoice` each expose a router with **no
test files whatsoever**, and each is marked COMPLETE. `employee` is precisely
the table whose missing GRANT caused a production-shaped outage that no test
caught.

### C7 — Reporting is unreachable: the router is never mounted

Found during the end-to-end documentation audit, not by any test.

`api/app.py:39` imports `reporting` alongside every other router, but the
corresponding `app.include_router(reporting.router, ...)` line **does not
exist** — there are 16 `include_router` calls and none of them is reporting.
The module is therefore dead code end to end:

- `routers/reporting.py` defines 4 endpoints under prefix `/reporting`
  (`/sales`, `/gst`, `/drivers`, `/consumption`)
- none appear in the generated OpenAPI spec (0 of 101 paths match `report`)
- `libs/reporting/data-access/reporting.store.ts` calls
  `/api/v1/reporting/{sales,drivers,consumption,gst}` — **all four 404**
- the `/reports` route and its nav entry are live, so the page is reachable
  and simply fails

No test caught this because Reporting has no tests (C4), and the unused import
does not trip ruff because the name *is* referenced in the import list.

Separately, `docs/data/11-api-contracts.md` documented these under
`/api/v1/reports/...` (plural) while the code uses `/reporting/...` — so the
contract doc would not have matched even once mounted. Corrected there.

**Fix is one line**, but it should land with tests, since mounting the router
exposes four previously unreachable endpoints to RBAC and RLS for the first
time. Tracked as R7a.

### C9 — Every user created since `8c221c3e0a91` had ZERO permissions ✅ RESOLVED (R11, 2026-08-18)

**A live production regression, found by R1 — not a test defect.**

Migration `8c221c3e0a91` changed permission resolution from **role-based** to
**per-user**. `SqlAlchemyPermissionRepository.has_permission` and
`get_permission_codes_for_user` now read only from
`identity.identity_user_permission`; neither consults `identity.role_permission`
or the user's `role` column any more.

The migration backfilled every user that existed at the time, which is why the
running app still works and why this went unnoticed. But:

- The **only** write path is `set_permissions_for_user`, called from exactly one place — `PUT /api/v1/admin/users/{id}/permissions`.
- **No user-creation path grants anything.** `InviteStaffUserUseCase` sets `role=` and stops. Customer registration and employee registration likewise.

So any staff member invited today can authenticate and then do **nothing** —
every `require_permission` check fails — until an administrator manually opens
their permission editor. Their role is set correctly and confers nothing.

`orders:cancel_approve` is granted to `agency_admin` in `role_permission`, and a
real `agency_admin` is still refused. That is the shape of the bug in one line.

> **Correction.** An earlier revision of this file attributed all 18 failures to
> stale `address_line` fixtures and stated product code was correct. That held
> for 11 of them. It then attributed the remaining 7 to this defect — also
> wrong. Diagnosing each of the 7 individually (rather than assuming a shared
> cause) found only 2 were actually C9. The other 5 split across two more
> defects, below, both unrelated to permissions.

**✅ Fixed 2026-08-18 (R11).** Both real creation paths — `InviteStaffUserUseCase`
and the `EmployeeRegistered` event handler — funnel through exactly one method,
`SqlAlchemyStaffUserRepository.add()`, so the fix lives there rather than in
either caller: `add()` now flushes the new `identity_user` row and inserts its
role's permissions from `role_permission` in the same transaction, before
returning.

Deliberately **not** a read-time fallback to `role_permission` in
`SqlAlchemyPermissionRepository` — the option this file originally
recommended. `PUT /admin/users/{id}/permissions` does a full delete-then-insert
of a user's *exact* permission set (`set_permissions_for_user`); a fallback
would mean an admin revoking a role-granted permission for one user, and
saving, would silently keep granting it from the role on every later read.
Materialising once at creation keeps that editor's contract intact: whatever
is in `identity_user_permission` for a user *is* their permission set, full
stop, including a deliberately-emptied one. This reversed the initial
recommendation after actually reading `set_permissions_for_user`'s semantics.

**Two more defects surfaced while closing this out — real, and now fixed —
initially mis-attributed to C9 by assuming a shared cause without checking:**

- **`get_unit_of_work` was swallowing every `DomainError` as an opaque 500.**
  `api/v1/dependencies/unit_of_work.py` caught `Exception` broadly and
  re-raised only `HTTPException`/`ApplicationError` unchanged — every business
  state-transition violation (order/route/inventory invalid-transition errors)
  got flattened into a generic 500 instead of `domain_error_handler`'s
  documented 409 with a real `error_code`. This dependency is used by 18
  files; the bug defeated the "well-formed request, not-currently-permitted
  state" contract almost everywhere a `UnitOfWork` is resolved. Fixed by
  adding `DomainError` to the re-raise tuple, matching the pattern already
  used for the other two types. Found because 3 of the 7 post-R1 failures
  shared this exact shape ("Cannot transition X from 'A' to 'B'" arriving as
  500, not 409) and had nothing to do with permissions.
- **Two RBAC "live check" tests used a synthetic `uuid.uuid4()` `user_id` with
  no backing row.**
  `TestLivePermissionCheckForReconciliationApprove::test_allows_a_real_warehouse_staff`
  and `TestLivePermissionCheckForOrdersCancelApprove::test_allows_a_real_agency_admin`
  predate the per-user model and asserted a live check succeeds for a role
  that holds the permission in `role_permission` — true under the old
  role-based check, structurally impossible under the per-user one, since
  `has_permission` requires a real row keyed to a real `user_id`. Fixed by
  seeding a real tenant + user + grant via a real `admin_engine_lpg_test`
  connection in both tests, rather than loosening product behaviour to match
  a stale test.

**Also fixed in the same pass, unrelated to C9:**
`test_admin_rbac.py::test_allows_a_real_super_admin` referenced a fixture,
`admin_engine_lpg_test`, that file never defined — a copy-paste omission
relative to the ~10 sibling files that each carry their own copy; added. That
test (and separately, R1's `test_identity_repositories.py` fix) hardcoded a
literal email instead of uuid-suffixing it like every neighbouring call site,
which flakes on any second local run against the same `lpg_test` database —
fixed at the source rather than papered over by clearing rows.
`test_customer_endpoints_smoke.py`'s KYC submission sent `doc_reference`
against a schema that has required `document_number` since it was written — a
stale key, fixed exactly like C1.

**R13 — ✅ RESOLVED, 2026-08-18.** `GET /api/v1/admin/tenant`
(`routers/admin.py`) had **no permission dependency at all** — only
`Depends(get_current_principal)` ("authenticated"), while every sibling
endpoint in the same router requires one (`rename_tenant` requires
`tenant:configure`). A seeded `driver` could call it and got `200` where
`test_a_driver_is_denied_admin_access` expects `403`.

Deliberately left open at the time rather than guessed at, since neither
option (add a permission code, or judge the endpoint intentionally ungated)
had an obvious answer. Resolved by adding a permission code —
`f3c8a56d29e1_add_tenant_read_permission.py`:

- New code `tenant:read`, granted to `super_admin`/`agency_admin`/`manager`/`dispatcher` — mirroring `a907e81bc74c`'s role list for `users:read`, the one existing precedent in this codebase for a comparable basic-info-read permission, rather than inventing a new list. `warehouse_staff`, `accountant`, `driver`, `customer` excluded, matching what the test asserts.
- Confirmed first: no frontend feature currently calls this endpoint (`AdminTenantService.getTenant` has zero callers outside the generated client), so gating it narrows nothing a real UI depends on today.
- **Backfilled `identity.identity_user_permission` for existing users of those roles in the same migration**, not just `role_permission` — the exact gap this session already found twice (`b4d19e7c3a52`, then C9/R11 itself). Since `8c221c3e0a91`, `has_permission` never consults `role_permission` at request time; a migration that only inserts there grants the new code to nobody who already exists. Landing this migration without that step would have reintroduced C9's bug for one more permission code on day one.
- Router changed to `Depends(require_permission("tenant:read"))`; `get_current_principal` remains used elsewhere in the same file.

Verified: `tests/integration` **253 passed, 0 failed**. `tests/unit` 514
passed, unchanged. mypy 18/6, import-linter 3 kept/2 broken, both unchanged —
confirming nothing outside this one endpoint moved. Applied to `lpg_dev`,
`lpg_test`, `lpg_uat`; **not yet applied to Supabase**.

### C10 — `get_unit_of_work` silently downgraded every domain error to 500 ✅ RESOLVED (R11, 2026-08-18)

Found while diagnosing the failures left after C9's fix, by actually reading
each one instead of assuming a shared cause — the earlier assumption that "all
7 remaining are C9" was wrong for 5 of them.

`api/v1/dependencies/unit_of_work.py::get_unit_of_work` wraps the request in a
broad `except Exception as e:`, and only re-raised `HTTPException` and
`ApplicationError` unchanged — everything else, including every `DomainError`
(`InvariantViolation`, `InvalidOrderStatusTransitionError`,
`InvalidStatusTransitionError`, …), was flattened into a generic
`HTTPException(500, ...)`. This directly defeats `domain_error_handler`'s
entire documented purpose (`middleware/problem_details.py`): a business-rule
violation is a well-formed request against a not-currently-permitted state and
should come back `409` with a stable `error_code`, not an opaque `500`.

`get_unit_of_work` is depended on by 18 files, so this was live on nearly
every mutating endpoint, not one corner case. Three integration tests caught
it independently — an order, a route, and an inventory location each hitting
an invalid state transition and getting `500` instead of `409` — before being
traced to one shared cause.

**Fixed** by adding `DomainError` to the tuple of exception types re-raised
unchanged, matching the pattern already used for `HTTPException`/
`ApplicationError`. `get_unit_of_work_factory` in the same file has no such
catch-all and was unaffected; no other dependency module repeats this pattern.

### C8 — Seven designed domain events were never implemented

Found by the documentation baseline audit (2026-08-18), verifying
`docs/data/09-domain-events.md` against `class X(DomainEvent)` declarations.

Of 18 events in the design catalog, 10 exist. One is a rename
(`OrderAssigned` → `OrderAssignedToRoute`, Phase 12). The other **seven are
genuine gaps** — the state change happens and publishes nothing, so nothing
downstream can react:

| Missing event | Domain | Consequence |
|---|---|---|
| `ComplaintRaised`, `ComplaintResolved` | `complaint` | **The complaint domain defines no events whatsoever.** Complaint handling carries SLA obligations, and there is nothing for a notification, escalation or audit projection to subscribe to. Delayed handling of a leakage complaint is a Major MDG irregularity. |
| `PaymentCollected`, `RefundApproved`, `CashShortfallDeclared` | `accounting` | Only `InvoiceGenerated` exists. Cash reconciliation and refund audit have no event trail. |
| `ConnectionClosed` | `customer` | Closure settlement (D-21) has no trigger. |
| `NotificationSent` | `notification` | Only `InAppNotificationCreated`; no delivery-confirmation event. |

Conversely 31 implemented events were undocumented; the catalog now lists all
of them by domain.

Tracked as **R10**. Not urgent in the way a red gate is, but it is the reason
several downstream features cannot be built without first adding the event.

### C5 — Lint / type debt

634 ruff errors (~190 auto-fixable), 23 mypy errors. Hotspots: `api/v1` 72,
`infra/persistence` 55, `infra/jobs` 43, `domain/complaint` 27,
`application/reporting` 26, `infra/events` 16, `domain/customer` 13.

### C6 — Process

169 uncommitted files; last commit 2026-08-15. Missing planning dirs for
Phase 11, 16, 17, Reporting and Employees.

## Remediation order

Sequenced by gate-failures-cleared per unit of work, not by module number.

- [ ] **R0** — Commit the working tree, so later fixes stay separable from in-flight work
- [x] **R1** — C1 fixture drift → **done 2026-08-18**, cleared 11 of 18; frontend follow-up cleared 2 more sites (blank dropdown, dead wizard field)
- [x] **R11** — C9 restore permissions for newly-created users → **done 2026-08-18**, plus C10 (see below) and 4 test-infra defects found while closing it out
- [x] **R13** — `GET /admin/tenant` had no permission dependency → **done 2026-08-18**, added `tenant:read` (super_admin/agency_admin/manager/dispatcher), backfilled existing users, gated the endpoint. `tests/integration`: 253/253 passing, 0 failed
- [ ] **R2** — C3 blank buttons → 2 files, user-visible bug
- [ ] **R3** — Frontend lint (7 projects) + `shell-layout.ts` lazy-import fix → also repairs `dashboard:test`
- [ ] **R4** — Frontend tests (4 projects)
- [ ] **R5** — C2 import contracts → decide `TYPE_CHECKING` policy, remove `text()` from API layer
- [ ] **R6** — `ruff --fix` the ~190 mechanical errors, then triage the remainder
- [ ] **R12** — onboarding wizard flattens structured address into one line before calling `addAddress`
- [ ] **R7a** — C7 mount the reporting router (one line) **with tests** — it exposes 4 endpoints to RBAC/RLS for the first time
- [ ] **R7** — C4 test coverage for complaint / reporting / employee / invoice
- [ ] **R8** — Backfill planning dirs for 11, 17, Reporting, Employees
- [ ] **R9** — Verify mobile CI (Phase 05 / 19) — not exercised in this pass
- [ ] **R10** — C8 add the 7 missing domain events, starting with the complaint pair

## Rules for updating this file

1. A row moves to ✅ only when its gates are **re-run and green**, with the output seen.
2. Do not mark a module's own `STATUS.md` COMPLETE without updating this file in the same change.
3. If a claim here is later disproven, correct the row and record what the evidence was — the history of wrong claims is the reason this file exists.
