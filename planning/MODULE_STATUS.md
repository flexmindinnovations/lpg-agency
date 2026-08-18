# Module Status — Verified Baseline

**Generated:** 2026-08-18 · **Last updated:** after R1 · **Migrations:** `e2a91c4f7b58` (all 4 environments)

## How this was produced

Every row was checked by running the project's own CI commands and reading the
code — not by reading `STATUS.md` files. Where a doc claim and the measured
result disagree, the measured result wins and the disagreement is recorded.

| CI command | Result |
|---|---|
| `uv run ruff check .` | **524 errors** (was 634; 109 of the drop is `backend/scratch/` now gitignored, 1 from R1 — not a code-quality improvement) |
| `uv run mypy` | **19 errors in 7 files** (was 23 in 10; R1 cleared 4) |
| `uv run lint-imports` | **2 of 5 contracts BROKEN** |
| `uv run pytest tests/unit` | 514 passed |
| `uv run pytest tests/integration` | **7 failed**, 245 passed, 1 error (was 18 failed / 234 passed before R1) |
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
| 06 | Auth & authorization | complete | 🔴 **live regression** | 100% | 🔴 | import-linter `routers/auth.py` → sqlalchemy | **Owns C9** — every user created since `8c221c3e0a91` has zero permissions. Test fixtures fixed in R1 |
| 07 | Admin / tenant master data | complete | 🟡 works, gates red | 100% | 🔴 | 1 fail + 1 **error** (both C9); lint: `admin-feature-flags`, `admin-feature-tenant-settings` | Frontend lint errors; test `NameError` fixed in R1 |
| 08 | Customer management | ✅ COMPLETE | 🟡 1 fail left | 100% | 🔴 | 1 integration fail (C9) | C1 fixture drift **fixed in R1** |
| 09 | Driver management | ✅ COMPLETE | ✅ | 100% | ✅ | — | — |
| 10 | Inventory management | ✅ COMPLETE | 🟡 2 fails left | 100% | 🔴 | 2 integration fails (both C9) | C1 portion cleared by R1 |
| 11 | Order management | complete (no planning dir) | 🟡 **7 of 8 fixed** | 100% | 🔴 | 1 integration fail (C9) | R1 cleared 7 of 8. `planning/features/11-order-management/` still **does not exist** |
| 12 | Delivery & dispatch | ✅ COMPLETE "verified independently" | 🟡 1 fail left | 100% | 🔴 | 1 integration fail (C9) | C1 portion cleared by R1 |
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

### C1 — `address_line` → `line_1` fixture drift ✅ RESOLVED (R1, 2026-08-18)

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

### C9 — 🔴 Every user created since `8c221c3e0a91` has ZERO permissions

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

This accounts for **all 7 remaining integration failures**. The tests were
correct and were detecting a real regression.

> **Correction.** An earlier revision of this file attributed all 18 failures to
> stale `address_line` fixtures and stated product code was correct. That held
> for 11 of them. The other 7 are this — a product bug the fixture fix simply
> uncovered.

**Not fixed here — it needs a design decision, not a patch:**

1. Does `role_permission` remain a fallback when a user has no explicit grants (restores old behaviour, keeps per-user overrides as additive), or
2. Does every creation path explicitly materialise the role's permissions (matches what the migration's backfill did, but every new creation path must remember to do it)?

Option 1 is more forgiving and matches how the docs describe RBAC. Option 2
matches the intent of the per-user table. Whichever is chosen must also cover
customer and employee registration, and needs a test that creates a user
through the *real* invite path and asserts it can act.

Tracked as **R11 — highest priority**, above the remaining lint work.

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
- [x] **R1** — C1 fixture drift → **done 2026-08-18**, cleared 11 of 18; exposed C9
- [ ] **R2** — C3 blank buttons → 2 files, user-visible bug
- [ ] **R3** — Frontend lint (7 projects) + `shell-layout.ts` lazy-import fix → also repairs `dashboard:test`
- [ ] **R4** — Frontend tests (4 projects)
- [ ] **R5** — C2 import contracts → decide `TYPE_CHECKING` policy, remove `text()` from API layer
- [ ] **R6** — `ruff --fix` the ~190 mechanical errors, then triage the remainder
- [ ] **R11** — C9 restore permissions for newly-created users 🔴 **highest priority — live regression**
- [ ] **R7a** — C7 mount the reporting router (one line) **with tests** — it exposes 4 endpoints to RBAC/RLS for the first time
- [ ] **R7** — C4 test coverage for complaint / reporting / employee / invoice
- [ ] **R8** — Backfill planning dirs for 11, 17, Reporting, Employees
- [ ] **R9** — Verify mobile CI (Phase 05 / 19) — not exercised in this pass
- [ ] **R10** — C8 add the 7 missing domain events, starting with the complaint pair

## Rules for updating this file

1. A row moves to ✅ only when its gates are **re-run and green**, with the output seen.
2. Do not mark a module's own `STATUS.md` COMPLETE without updating this file in the same change.
3. If a claim here is later disproven, correct the row and record what the evidence was — the history of wrong claims is the reason this file exists.
