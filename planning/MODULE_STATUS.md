# Module Status — Verified Baseline

**Generated:** 2026-08-18 · **Last updated:** after R6 · **Migrations:** `f3c8a56d29e1` (local `lpg_dev`/`lpg_test`/`lpg_uat`; Supabase not yet migrated)

## How this was produced

Every row was checked by running the project's own CI commands and reading the
code — not by reading `STATUS.md` files. Where a doc claim and the measured
result disagree, the measured result wins and the disagreement is recorded.

| CI command | Result |
|---|---|
| `uv run ruff check .` | **73 errors** (was 634) — all in `migrations/versions/*.py` (accepted debt, never reformatted) or 4 deliberately-unchanged `UP042`s (see C5) |
| `uv run mypy` | **0 errors** (was 23 in 10 files) |
| `uv run lint-imports` | **0 of 5 contracts broken** (was 2 broken) |
| `uv run pytest tests/unit` | 514 passed |
| `uv run pytest tests/integration` | **0 failed**, 253 passed (was 18 failed / 234 passed originally) |
| `npx nx run-many -t lint` | **0 of 26 projects fail** (was 7 of 24) |
| `npx nx run-many -t test` | **0 of 25 projects fail** (was 4 of 23 — see R3/R4) |
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
| 14 | Accounting / invoicing | ✅ COMPLETE | 🔴 untested | ~90% | 🔴 | — | **No invoice endpoint tests, no accounting integration tests.** Blank buttons fixed (C3/R2) |
| 15 | Notifications | Backend COMPLETE | 🟡 tested, gates red | 100% | 🔴 | lint + test: `notification-feature-notifications` | Frontend lint and unit tests failing |
| 17 | Complaint management | ✅ COMPLETE (in `current_phase`) | 🔴 **zero backend tests** | ~90% | 🔴 | test: `feature-complaints` (pre-existing Jest/ESM gap, unrelated to markup); import-linter `routers/complaint.py` → sqlalchemy; ruff `domain/complaint` 27 | Full aggregate + router with **no tests at all**; blank buttons fixed (C3/R2); no planning dir |
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

### C2 — Clean Architecture contracts (2 of 5 broken) ✅ RESOLVED (R5, 2026-08-18)

Re-running `uv run lint-imports` before touching anything showed the real
scope was much larger than this row's original description: not 3 router
sites, but **3 genuine router-level violations plus 11 composition-root-shaped
ones** the original sweep never enumerated (some pre-existing and missed,
some from modules — accounting, driver events, employee repo — that shipped
after C2 was first written).

**Genuine violations (3), each a router reaching around its own
`UnitOfWork`/dependency-injection seam into raw SQLAlchemy or infrastructure
types directly:**

- `routers/auth.py`'s `_resolve_tenant_id` ran `session.execute(text("SELECT
  tenant.auth_resolve_tenant_id_by_slug(:slug)"))` directly against a session
  pulled via a deferred `lpg.api.app` import — no port, no injection. Added
  `TenantSlugResolver` (`application/identity/ports.py`), implemented by
  `SqlAlchemyTenantSlugResolver` (`infrastructure/identity/`), wired via a
  new `get_tenant_slug_resolver()` in `dependencies/identity.py` — same
  shape as every other `get_*_repository()` in that file. `otp_request`/
  `otp_verify` now take it as a real `Depends()` parameter.
- `routers/complaint.py`'s `get_complaint`/`list_complaints` did
  `getattr(uow, "_uow", uow)` then `getattr(uow_impl, "session")` to
  hand-roll `select(ComplaintModel)` queries with eager-loading and
  pagination — bypassing `ComplaintRepository` entirely, even though
  `get_by_id` already existed on it and did the identical eager-loaded
  query. Added `list_complaints`/`count_complaints` to `ComplaintRepository`
  (domain port) and `SqlAlchemyComplaintRepository` (extracting a shared
  `_to_domain()` helper from the pre-existing `get_by_id` mapping code), and
  rewrote both endpoints to call `uow.complaints.*` — the accessor the
  DI wrapper (`dependencies/complaint.py::_ComplaintUnitOfWorkWrapper`)
  already exposed and the router had been reaching around.
- `routers/notifications.py` repeated the identical
  `getattr(uow, "_uow", uow)` / `getattr(uow_impl, "session")` hack on
  **all four** endpoints to build `SqlAlchemyInAppNotificationRepository`
  by hand. Added `dependencies/notification.py::get_notification_repository()`
  (same composition-root shape as every other dependency-wiring module) and
  switched all four endpoints to `Depends()` it instead.

**Composition-root-shaped violations (11):** `dependencies/accounting.py`,
`dependencies/admin.py` (the employee repository — added after the last
audit), `dependencies/complaint.py`, `dependencies/reporting.py`, and two
`lpg.api.app` domain-event-handler registrations (`accounting_handlers`,
`tenant_admin_handlers`) — all structurally identical to the dozen+ entries
this contract's `ignore_imports` already accepted for identity/admin/
customer/delivery/inventory/order. Added matching entries rather than
touching the code — this **is** the composition root's documented role.

**`realtime/connection_manager.py`'s FastAPI import — inverted, not
ignored.** The only thing this module actually calls on `WebSocket` is
`.send_json(...)`. Replaced the `TYPE_CHECKING`-guarded `from fastapi import
WebSocket` with a local, structural `Protocol` (`class WebSocket(Protocol):
async def send_json(self, data: Any) -> None: ...`) — `fastapi.WebSocket`
satisfies it with zero explicit coupling in either direction, matching this
codebase's existing `TenantResolver`/`RealtimePublisher` dependency-inversion
idiom rather than just suppressing the check.

Verified: `uv run lint-imports` — **0 of 5 contracts broken** (was 2).
`uv run mypy` on every touched file — 0 issues. `uv run pytest tests/unit`
— 514 passed, unchanged. `uv run pytest tests/integration` — **253 passed,
0 failed**, unchanged. Backend-wide `uv run ruff check .` moved 524→481
(incidental — import-block reordering `ruff --fix` picked up in files
already being edited here; the remaining count is R6's scope, untouched).

### C3 — PrimeNG v22 blank buttons ✅ RESOLVED (R2, 2026-08-18)

`<button pButton icon="…" label="…">` — both attributes are **no-ops on the
directive**; they exist only on the `<p-button>` *component*. Correct pattern
is `<i pButtonIcon>` + `<span pButtonLabel>`; the label span is required, or
`ButtonDirective.isIconOnly` collapses the button.

Fixed both sites, and they turned out to be two different failure modes, not
one:

- `feature-invoices.html:114,122` — icon **and** label attributes, matching C3's original description exactly: fully empty buttons.
- `feature-complaints.html:134-148` (`Assign`/`Resolve`) — `icon="…"` attribute only, with plain-text content already present (`>Assign</button>`, no `label=`). The icon silently never rendered, but the text did — a smaller defect than the fully-blank case, and one the original sweep's regex would have caught (it matched on `icon=` OR `label=`) but the earlier description didn't distinguish. Found by reading each site rather than assuming both matched the same pattern.

Re-swept the whole frontend afterward (`grep` for `pButton` combined with
`icon=`/`label=` across every `.html`) — zero remaining occurrences.
`feature-invoices`/`feature-complaints` lint clean; `nx build dashboard`
succeeds. `feature-complaints:test` still fails, but confirmed via `git
stash` that the exact same `SyntaxError: Unexpected token 'export'` fails
identically with or without this change — pre-existing Jest/ESM config gap,
tracked as R4, not caused or fixed here.

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

### C11 — Frontend lint: 7 of 24 projects failing ✅ RESOLVED (R3, 2026-08-18)

Mechanical fixes, one per project, all confirmed by re-running
`npx nx run-many -t lint --skip-nx-cache`:

- `notification-bell.ts`/`notification-drawer.ts` — `selector: 'lpg-*'` →
  `'lib-*'` (`@angular-eslint/component-selector`, prefix must be `lib`);
  `notification-bell`'s `@Output() toggle` renamed to `toggled`
  (`no-output-native` — `toggle` collides with a real DOM event name), with
  the two call sites in `shell-layout.ts` updated to match.
- `notification-drawer.html` — `*ngIf`/`*ngFor` converted to `@if`/`@for`
  (`template/prefer-control-flow`); `*ngFor` uses `track notification.id`.
- `feature-employees.ts` — same selector-prefix fix.
- `feature-flag-overrides-page.ts` — removed an empty `ngOnInit(): void {}`
  and the now-unused `OnInit` import (`no-empty-lifecycle-method` +
  `no-empty-function`).
- `cylinder-types-page.ts`, `price-list-page.ts`,
  `tenant-configuration-page.ts` — stripped a stray UTF-8 BOM
  (`\xEF\xBB\xBF`) that had leaked into line 2 of each file
  (`no-irregular-whitespace`).
- `reporting/data-access/project.json` — had `"tags": []`; the boundary rule
  couldn't match an untagged dependency against the allowed-list, breaking
  `reporting-feature-reports`. Tagged `["type:data-access", "scope:reporting"]`.

**The `shell-layout.ts` lazy-import violation was architectural, not
mechanical.** `tsconfig.base.json` had `@lpg/notification/ui-bell` and
`@lpg/notification/ui-drawer` path aliases pointing at *individual files
inside* `libs/notification/feature-notifications/` — the same Nx project as
the lazy-loaded notifications-list route. Nx's module graph operates at the
project (folder) level, not the file level, so any static import through
those aliases from `shell-layout.ts` registered as a static import of the
whole lazy-loaded project, tripping `@nx/enforce-module-boundaries`'s
"static import of a lazy-loaded library" rule.

Fixed by physically splitting `notification-bell`/`notification-drawer` into
two new genuine Nx libraries — `notification-ui-bell`,
`notification-ui-drawer` — matching the alias names that were already
chosen in `tsconfig.base.json` (apparently unexecuted original intent). Both
components inject `NotificationService`/`WebSocketService` and own real
side effects (WebSocket subscriptions, HTTP calls), so despite the `ui-*`
directory name they're tagged `type:feature`, not `type:ui` — `type:ui` may
only depend on `type:util`/`type:design-tokens` per the boundary rules, and
tagging them `type:ui` first produced two new boundary violations of the
same kind this fix was meant to remove. `type:app` (dashboard) is permitted
to depend on `type:feature` libraries, same as `type:ui` ones, so the retag
resolved it with no behavioral change.

Verified: `npx nx run-many -t lint --skip-nx-cache` — **0 of 26 projects
fail** (2 more projects than the original 24, from the library split), only
pre-existing unrelated warnings remain. `npx nx build dashboard` succeeds.

**Did not repair `dashboard:test`, despite the original R3 line saying it
would** — that was a wrong assumption. `shell-layout.spec.ts` fails on `No
provider found for _ConfirmationService`, confirmed via `git stash` on just
`shell-layout.ts` to fail identically with or without this change: a
pre-existing test-harness gap unrelated to the lazy-import fix, not
previously tracked. Added to R4's scope below.

Also surfaced: splitting `notification-feature-notifications`'s spec file
into three project-local spec files means the workspace's one pre-existing
`SyntaxError: Unexpected token 'export'` Jest/ESM failure (R4, first found
via `feature-complaints:test`) now fails independently in
`notification-ui-bell`, `notification-ui-drawer`, and
`notification-feature-notifications` — three failing projects, not a new
defect three times over. Confirmed via `git stash -u` that
`notification-feature-notifications:test` failed identically before the
split. `npx nx run-many -t test` moved from 4-of-23 failing to 6-of-25: +2
from this one Jest/ESM defect now counted per-project, plus
`shared-data-access:test` (pre-existing, unrelated to R3 — `auth.interceptor.spec.ts`
expects an `/api/v1/orders` retry request that never fires; not investigated
further here).

### C12 — Frontend tests: 6 of 25 projects failing ✅ RESOLVED (R4, 2026-08-18)

Three distinct defect classes, all confirmed by re-running
`npx nx run-many -t test --skip-nx-cache`:

**1. Jest/ESM `transformIgnorePatterns` gap (4 projects: `feature-complaints`,
`notification-feature-notifications`, `notification-ui-bell`,
`notification-ui-drawer`).** Every other project's `jest.config.cts` has
`transformIgnorePatterns: ['node_modules/(?!(@primeui|@noble)|.*\\.mjs$)']`
— these 4 (plus `reporting/data-access` and `reporting/feature-reports`,
latent but not yet triggering) still had the older
`['node_modules/(?!.*\\.mjs$)']`, which doesn't transform `@primeui`'s
license-manager or `@noble/ed25519`'s ESM `.js` files, so Jest hit
`SyntaxError: Unexpected token 'export'` the moment a component imported
PrimeNG's `badge`/`drawer` modules. Fixed all 6 to match the workspace
standard.

**2. Spec files that never successfully ran before, so were never caught
missing TestBed providers their components actually need** — the ESM
crash above happened *before* any test body executed, masking these:
`notification-bell`/`notification-drawer`/`notification-feature-notifications`
inject `NotificationService` (HTTP), and `notification-drawer` renders a
`RouterLink`, and `notification-feature-notifications` injects `MessageService`
— none of it wired into the specs' `TestBed.configureTestingModule`. Added
`provideHttpClient()` + `provideHttpClientTesting()` + a stub
`ApiConfiguration`, `provideRouter([])`, and `MessageService`, matching the
pattern already established in `feature-vehicles.spec.ts` and
`profile-menu.component.spec.ts`.

**3. Two independent, already-latent gaps surfaced once the above unblocked
their projects:**
- `shell-layout.spec.ts` (`dashboard`) — `No provider found for
  _ConfirmationService`; `shell-layout.ts` renders `<p-confirmDialog>` but
  the spec only provided `MessageService`. Added `ConfirmationService`.
- `app.spec.ts` (`dashboard`) — two tests asserting stale Phase-1
  invariants: `shellRoute?.component` (the shell route now uses
  `loadComponent`, lazy-loaded, not `component`) and a `businessPaths` list
  (`delivery`, `accounting`, `ledger`, `complaints`, `reports`) that had
  already shipped for every module it named — 3 of the 5 entries never
  matched real path segments to begin with (the real ones are
  `drivers`/`vehicles`/`dispatch`, `invoices`, `ledger/:customerId`), so
  those were always vacuously passing; only `complaints` and `reports`
  literal-matched and now fail because those modules are live. Fixed the
  first assertion to check `loadComponent`, and replaced "contains no
  business routes" with a test of the invariant that's actually still true
  and worth guarding: every child route other than `''`/`profile`/
  `notifications`/`**` carries a `canActivate` guard — following the same
  incremental-retirement precedent this file already used for `orders`.
- `auth.interceptor.spec.ts` (`shared-data-access`) — `authInterceptor`
  gained `Router` and `ConfirmationService` injections (for the
  session-expired re-login dialog) that the spec's providers never picked
  up, so `inject()` threw before any request reached the test backend,
  failing all 4 tests with "found none". Added the two providers. The
  fourth test also asserted stale behavior — expecting the observable to
  error on a repeat refresh failure, when the interceptor deliberately
  `return EMPTY`s in that case (per its own inline comment, so
  `problemDetailsInterceptor` doesn't show a second, generic toast on top
  of the confirm dialog). Rewrote the assertion to match the documented
  contract: no error, the observable completes, the session is cleared,
  and `ConfirmationService.confirm` is called with the session-expired
  dialog.
- `libs/shared/data-access/src/lib/services/notification.spec.ts` — dead
  scaffold, unrelated to the fixes above. Imported a class named
  `Notification` that doesn't exist in `notification.ts` (only
  `NotificationService` does — presumably renamed early to avoid
  colliding with the browser's global `Notification` API), so the import
  silently resolved to `undefined` and `TestBed.inject(undefined)` threw.
  Never tested anything real; deleted rather than fixed forward, since
  writing a new spec for `NotificationService` is new coverage (R7's
  scope), not a fix for this one.

Verified: `npx nx run-many -t test --skip-nx-cache` — **0 of 25 projects
fail** (was 6). `npx nx run-many -t lint` and `npx nx build dashboard`
re-confirmed still green after these changes.

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

### C5 — Lint / type debt ✅ RESOLVED (R6, 2026-08-18)

Started this pass at 481 ruff errors, 2 mypy errors (both already reduced
from the original 634/23 baseline by R1–R5's incidental cleanup of files
they happened to touch).

**`ruff check --fix` + `ruff format src tests`** cleared the vast majority
mechanically: import sorting, unused imports, trailing/blank-line
whitespace, `Optional[X]` → `X | None`, deprecated-import updates,
`__slots__`/dunder-`__all__` sort order, and line wrapping via the
formatter (which fixed most of the ~190 originally-estimated `E501`s as a
side effect — genuinely fixing 112 line-length violations that
`ruff check --fix` alone can't touch, since it isn't a rewrapping tool).
Migrations picked up `ruff check --fix`'s safe pass too (import sorting,
unused-import removal, `Union[X, None]` → `X | None` — confirmed zero SQL/DDL
content changed, import statements only) but were deliberately excluded
from the `ruff format` rewrap: they're historical, already-applied
artifacts, and reformatting ~10 of them for pure line-length style would
be diff noise on files this codebase's own convention already treats as
frozen. Their remaining 59 `E501` + 8 `W291` + 2 `E402`
are accepted debt, left as-is.

**One real regression, caught by the test suite, not by lint:**
`ruff --unsafe-fixes` (used for `TC001`/`TC003`, "move type-only imports
behind `TYPE_CHECKING`") applied the exact footgun `routers/*.py` and
`dependencies/*.py` already carry a written exemption for in
`pyproject.toml` — except this time against **SQLAlchemy's declarative
`Mapped[X]` columns** and **Pydantic's `BaseModel` field types**, not
FastAPI's `Depends()`. Both frameworks resolve `from __future__ import
annotations`-deferred type hints at class-definition/`model_rebuild()`
time; a name hidden behind `TYPE_CHECKING` is invisible to that resolution
exactly like it is to FastAPI's `get_type_hints()`. First symptom: `uv run
pytest tests/unit` failed 6 tests with `NameError: name 'Decimal' is not
defined` inside SQLAlchemy's mapper configuration
(`models/accounting.py`). Fixed by reverting to real imports there (2
model files), matching every other `models/*.py` file's existing
per-line `# noqa: TC003` convention. **A second instance of the same class
surfaced only in `tests/integration`**, not `tests/unit`:
`schemas/notification.py`'s `NotificationResponse` failed with Pydantic's
"is not fully defined; you should define `uuid`, then call
`model_rebuild()`" at request time — `uuid`/`datetime` had been moved
behind `TYPE_CHECKING` too. This one had already been documented as a
known rule in *other* schema files (`schemas/order.py`,
`schemas/inventory.py`, both carry a written note), just never turned into
an enforced exemption — added `"src/lpg/api/v1/schemas/*.py" =
["TC001","TC002","TC003"]` to `pyproject.toml` to make it one, alongside
the routers/dependencies entries it mirrors.

**Three real, pre-existing bugs found while reading the flagged code, none
related to formatting:**
- `dependencies/identity.py::require_permission` had a debug message
  assignment (`msg = "DEBUG FAIL: ..."` dumping `type()` reprs) that
  silently overwrote the intended clean `PermissionDeniedError` text —
  every 403 on this path leaked internal type information instead of the
  intended message. Deleted the dead debug line.
- `barcode_generator.py::generate_qr_png(data, *, size=200)` never
  applied `size` — every QR code was generated at a fixed native
  resolution regardless of the caller's request. Confirmed low visual
  impact (the one call site, `pdf_renderer.py`, embeds it in a template
  that hardcodes `width:120px;height:120px` via CSS) but still dead,
  misleading code; fixed by resizing the output image to `size` × `size`.
- `routers/employee.py::list_employees` accepted a `status` query
  parameter and silently discarded it — `ListEmployeesQuery` had no
  `status` field at all, so the filter was broken at every layer, not
  just the router. Wired it through `ListEmployeesQuery` →
  `ListEmployeesUseCase` → `EmployeeRepository.list_employees`/
  `.count_employees` (port + SQLAlchemy implementation), mirroring the
  existing `role`/`branch_id` filter pattern exactly. Also removed a
  `print(f"Error: {e}"); raise e` debug try/except in
  `ListEmployeesUseCase.execute` that added nothing (bare re-raise,
  `print` instead of the logger) — found in the same file while wiring
  the filter through.
- `infrastructure/events/realtime_handlers.py::on_order_status_changed`
  computed a `status` string from the event class name but never added it
  to the published WebSocket message — confirmed against
  `test_realtime_publisher.py`'s own expected message shape
  (`{"status": "delivered", ...}`), which the handler had never actually
  produced. Added the missing key.

**Judgement calls to leave alone:** `UP042` (`class X(str, Enum)` →
`StrEnum`, 4 occurrences in `domain/complaint/value_objects.py`) —
`StrEnum.__str__` returns the bare value while `(str, Enum)`'s default
`__str__` returns `"ClassName.MEMBER"` (only `__format__`/f-strings match
today); changing the base class is a real, if probably-safe, behavioral
change to string serialization this task's mechanical-cleanup scope
shouldn't absorb without dedicated verification of every consumer.

Verified: `uv run ruff check .` — 73 errors, all either accepted migration
debt or the deliberately-left `UP042`s. `uv run mypy` — **0 errors** (was
2, both cleared: `storage/client.py`'s two `# type: ignore` comments were
themselves unused, per mypy). `uv run lint-imports` — 5/5 kept, unchanged.
`uv run pytest tests/unit` — 514 passed. `uv run pytest tests/integration`
— **253 passed, 0 failed**, unchanged.

### C6 — Process

169 uncommitted files; last commit 2026-08-15. Missing planning dirs for
Phase 11, 16, 17, Reporting and Employees.

## Remediation order

Sequenced by gate-failures-cleared per unit of work, not by module number.

- [ ] **R0** — Commit the working tree, so later fixes stay separable from in-flight work
- [x] **R1** — C1 fixture drift → **done 2026-08-18**, cleared 11 of 18; frontend follow-up cleared 2 more sites (blank dropdown, dead wizard field)
- [x] **R11** — C9 restore permissions for newly-created users → **done 2026-08-18**, plus C10 (see below) and 4 test-infra defects found while closing it out
- [x] **R13** — `GET /admin/tenant` had no permission dependency → **done 2026-08-18**, added `tenant:read` (super_admin/agency_admin/manager/dispatcher), backfilled existing users, gated the endpoint. `tests/integration`: 253/253 passing, 0 failed
- [x] **R2** — C3 blank buttons → **done 2026-08-18**, 2 files, 2 distinct failure modes (fully blank vs. icon-only-missing)
- [x] **R3** — Frontend lint (7 projects) + `shell-layout.ts` lazy-import fix → **done 2026-08-18**, 0 of 26 projects fail. Did *not* repair `dashboard:test` (wrong original assumption, corrected in C11); that failure is now folded into R4
- [x] **R4** — Frontend tests → **done 2026-08-18**, 0 of 25 projects fail (was 6). Three defect classes: a `jest.config.cts` `transformIgnorePatterns` gap on 6 projects (4 actually failing), TestBed provider gaps never caught because those specs never previously ran to completion, and two independent stale-assertion / missing-provider bugs surfaced once unblocked (`dashboard`, `shared-data-access`). Full writeup in C12
- [x] **R5** — C2 import contracts → **done 2026-08-18**, 0 of 5 contracts broken (was 2). New `TenantSlugResolver` port replaces `routers/auth.py`'s raw `text()`; `ComplaintRepository`/`InAppNotificationRepository` gained list/count methods and proper DI wiring replacing two routers' raw-session hacks; 11 composition-root-shaped edges added to `ignore_imports`; `connection_manager.py`'s FastAPI import inverted into a local `Protocol`. Full writeup in C2
- [x] **R6** — `ruff --fix` the ~190 mechanical errors, then triage the remainder → **done 2026-08-18**, 481→73 errors, mypy 2→0. Found and fixed 3 real pre-existing bugs while triaging (leaked debug text in a 403 message, a QR-code `size` param silently ignored, an employee list `status` filter accepted but never applied at any layer) and caught+reverted a real regression `ruff --unsafe-fixes` introduced (SQLAlchemy/Pydantic runtime annotation resolution, same footgun class as FastAPI's `Depends()` — now a real `pyproject.toml` exemption for `schemas/*.py`, not just a comment). Full writeup in C5
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
