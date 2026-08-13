# Current Project Status

## Purpose

This document provides the current implementation status of the LPG Agency Management Platform.

It is a **summary**. The authoritative, always-current record is [`planning/current_phase.md`](../planning/current_phase.md). If the two ever disagree, that file wins and this one is stale.

This document is updated after every major milestone.

---

# Project Information

**Project:** LPG Agency Management Platform

**Architecture:** Clean Architecture · Domain Driven Design · Modular Monolith · Multi-Tenant SaaS

**Technology Stack**

| Layer | Technology |
|---|---|
| Backend | Python 3.13+, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2 |
| Database | PostgreSQL on **Supabase** (managed host only, ADR-027); RLS tenant isolation |
| Cache / Queue / Real-time | Redis |
| Web Dashboard | Angular 22 in an Nx workspace (`frontend/`), Signals + NgRx SignalStore, PrimeNG (primary) + Angular CDK (Material selective), Tailwind CSS v4, AG Grid Community (Enterprise optional per feature) |
| Mobile | Flutter, Riverpod, Drift SQLite (Driver App offline-first) |
| Real-Time | FastAPI WebSockets + Redis Pub/Sub |
| Container / CI / Cloud | Docker, GitHub Actions, Azure (hosting topology deferred) |

---

# Overall Progress

| Area | Status |
|--------|--------|
| Business Analysis | ✅ Complete |
| Software Requirements Specification | ✅ Complete |
| Solution Architecture | ✅ Complete (reconciled to Python/FastAPI, Phase 0) |
| Architecture Decision Records | ✅ Complete (ADR-001 … ADR-037) |
| Data Architecture | ✅ Complete |
| API Contracts | ✅ Complete |
| UX Architecture | ✅ Complete |
| Design System | ✅ Complete |
| Engineering Standards | ✅ Complete |
| **Documentation Reconciliation (Phase 0)** | ✅ **Complete — 2026-08-09** |
| **Repository / Development Foundation (Phase 1)** | ✅ **Complete — 2026-08-09** |
| **Backend Foundation (Phase 2)** | ✅ **Complete — 2026-08-09** |
| **Shared Infrastructure (Phase 3)** | ✅ **Complete — 2026-08-09** |
| **Angular Web Foundation (Phase 4)** | ✅ **Complete — 2026-08-09** |
| **Flutter Application Foundations (Phase 5)** | ✅ **Complete — 2026-08-09** |
| **Authentication & Authorization (Phase 6)** | ✅ **Complete — 2026-08-10** |
| **Administration & Tenant/Master Data (Phase 7)** | ✅ **Complete — 2026-08-10** |
| **Customer Management (Phase 8)** | ✅ **Complete — 2026-08-10** |
| **Driver Management (Phase 9)** | ✅ **Complete — 2026-08-10** |
| **Inventory Management (Phase 10)** | ✅ **Complete — 2026-08-11** |
| **Order Management (Phase 11)** | ✅ **Complete — 2026-08-12** |
| **Delivery & Dispatch (Phase 12)** | ✅ **Complete — 2026-08-13** |
| Backend Development | 🔨 Delivery/Dispatch (Phase 12) + Order Management (Phase 11) + Inventory (Phase 10) + Driver Management (Phase 9) + Customer (Phase 8) + Admin/master-data (Phase 7) + Identity (Phase 6) delivered |
| Frontend Development | 🔨 Dispatch Board (Phase 12) + Order UI (Phase 11) + Inventory UI (Phase 10) + Delivery UI (Phase 9) + Customer UI (Phase 8) + Admin UI (Phase 7) + Auth UI (Phase 6) delivered |
| Mobile Development | 🔨 Auth wired into both apps (Phase 6) — Admin, Customers, Drivers, Inventory, Orders, Dispatch are Dashboard-only in this phase |
| Testing | 🔨 Harness in place — backend unit suite passing (486 in Phase 12's own re-run; grows each phase), Phase-12-scope integration tests 39/39; `dashboard` lint/build clean |
| Deployment | 🔨 CI validation only — no deployment pipelines |

---

# Current Phase

**Completed:** Phase 12 — Delivery & Dispatch (started 2026-08-12, genuinely finished 2026-08-13 after a false "complete" claim was caught and corrected by an independent audit)

**Next:** Phase 13 — Cylinder Ledger.

Phase 12 made `Route`/`RouteStop` the real dispatcher-facing grouping construct, replacing Order Management's interim `driver_id`/`vehicle_id` columns on `Order` with a `route_stop_id` FK. Ships: a hardened `Route` aggregate (empty-route guard, `cancel_stop`/`reschedule_stop`, an auto-complete rule that transitions a route to `Completed` the instant every stop reaches a terminal status, no manual action needed), a rewritten migration (RLS, CHECK constraints, audit columns, real permission codes replacing two that were never seeded), `AssignOrderToRouteUseCase`/`LoadVehicleForRouteUseCase`/`CompleteRouteReconciliationUseCase` (the latter two deliberately reuse Inventory Management's existing load-transfer and reconciliation infrastructure rather than duplicating it — `VehicleLoadEvent`/`VehicleShiftReconciliation`, named in the original design, were never built; see `docs/data/01-domain-model.md` §4.4's divergence note), the full `/routes` REST surface with role-scoped RBAC, and a Dispatch Board rebuilt from a list+create stub into a real operational screen (status-column route board, a Route Detail drawer with Load/Start/Cancel/Reconcile actions, an unassigned-orders panel with click-to-assign). An independent audit on 2026-08-12 had caught the phase's first "COMPLETE" claim as false — zero tests, a broken `import-linter` contract, most of the frontend missing — and every one of those gaps is now closed and independently re-verified, not self-reported: static gates re-run by hand, 486 unit + 39 Phase-12-scope integration tests re-run by hand, and a live-browser pass through the real Dispatch Board (plan a route across two real branches to prove a hardcoded-first-branch bug is actually fixed, assign an order, load a vehicle, start the route, cancel the order and watch the route auto-complete with zero manual action, then confirm reconciliation is correctly blocked with a 409 until an approved reconciliation record exists). Full detail: [`planning/features/12-delivery-dispatch/STATUS.md`](../planning/features/12-delivery-dispatch/STATUS.md).

Phase 11 (Order Management, 2026-08-12) delivered the `orders` bounded context: a 10-state `Order` aggregate (`draft → booked → confirmed → assigned → ready_for_dispatch → out_for_delivery → delivered → closed`, plus `failed_delivery`/`cancelled` branches), BR-04/BR-19 policy ports (cylinder-cap and credit-limit checks, stubbed permissively pending Phase 13/14's real implementations), a tenant-configurable cancellation fee reusing Phase 7's historized `TenantConfiguration` resolver, Idempotency-Key-protected creation and delivery endpoints, and a two-slice Angular UI (Order Queue, detail/timeline, create-booking drawer with a new customer autocomplete, then the full dispatch-pipeline of action drawers — confirm/assign/dispatch/depart/deliver with signature+photo+GPS+OTP capture/failed-delivery/reschedule/cancel/close). At the time this phase shipped, `assign` still wrote raw `driver_id`/`vehicle_id` columns onto `Order` as a deliberate, documented interim simplification — Phase 12 (above) is what replaced that with the real `Route`/`RouteStop` relationship the migration's own docstring had always called for.

Phase 10 delivered the `inventory` bounded context across the backend and the Dashboard: `InventoryLocation` aggregate (warehouse/vehicle cylinder balances by type × status), goods receipt (GRN), atomic warehouse→vehicle load transfers, delivery/collection, status changes, manual adjustments, and reconciliation (create + live-checked approve), RBAC permissions (`inventory:read`, `inventory:load`, `inventory:adjust`, `reconciliation:approve`), 10 REST endpoints, OpenAPI contract, and a lazy-loaded Angular UI (`@lpg/inventory/feature-inventory` — location picker, balance grid, transaction history, 6 action drawers). Every mutating use case resolves its aggregate by `(location_type, location_ref_id)` rather than an opaque id, so a never-touched warehouse/vehicle returns an all-zero balance rather than 404 — a deliberate refinement over the documented `/inventory-locations/{location_id}/...` contract, which had no way for a client to discover an id before the first mutation. Independent verification against a real database (not just self-reported gate status) found and fixed three real defects before the automated test suite existed to catch them: a migration that would have double-seeded already-existing Phase 6 permission grants, a repository bug producing duplicate rows when two mutations in one `save()` touched the same balance key, and a missing `Computed()` marker on a DB-generated column that crashed the reconciliation-approval path. 511 backend tests, `mypy --strict`/`ruff`/`import-linter` clean, live-verified end to end in the browser. Pre-existing, unrelated frontend failures (predating this phase, confirmed via `git diff`) were found and flagged separately rather than fixed here. Full detail: [`planning/features/10-inventory-management/STATUS.md`](../planning/features/10-inventory-management/STATUS.md).

Phase 9 delivered Driver Management across the backend and the Dashboard: `Driver` and `Vehicle` aggregate roots, RLS isolation policies, application use cases, RBAC permissions (`drivers:read`, `drivers:manage`, `vehicles:read`, `vehicles:manage`), OpenAPI contract, Angular UI libraries (`feature-drivers` and `feature-vehicles`), lazy-loaded routes and sidebar navigation links. The original implementation's self-reported "100% passing" gates were false (`ruff check` had 4 real errors); an independent review-and-fix pass found and fixed that plus a missing FK/unique constraint, fabricated API response timestamps, an unreachable status-update modal, invisible/unclickable buttons (wrong PrimeNG API usage), and broken dark-mode theming from non-existent CSS token references. 455 backend tests, `mypy --strict`/`ruff`/`import-linter` clean, frontend lint/test/build clean, live-verified in-browser. Full detail: [`planning/features/09-driver-management/STATUS.md`](../planning/features/09-driver-management/STATUS.md).

Phase 7 (Administration & Tenant/Master Data, 2026-08-10) delivered master data for tenants to configure and a way to administer their own staff, across the backend and the Dashboard only (no mobile scope): Branch, Warehouse, Cylinder Type, historized Tenant Configuration and Price List, a full platform+tenant feature-flag system, staff user management, and a cursor-paginated audit-log read API. A documented divergence from `01-domain-model.md` §4.1: Branch/Warehouse/TenantConfiguration/CylinderType/PriceListEntry became independent aggregate roots.

Phase 6 (Authentication & Authorization, 2026-08-10) delivered a complete, hand-built Identity module across all three stacks: JWT (RS256, `pyjwt[crypto]`) + Argon2id password auth, OTP login for Customer/Driver, RBAC (claims-based + live DB re-query for four high-sensitivity actions), password reset — under strict per-tenant RLS via narrowly-scoped `SECURITY DEFINER` PostgreSQL functions (ADR-035). Replaces Phase 2's interim `HeaderTenantResolver`; closes DW-12. Full detail: [`planning/features/06-authentication-authorization/STATUS.md`](../planning/features/06-authentication-authorization/STATUS.md).

Phases 3 (Shared Infrastructure), 4 (Angular Web Foundation) and 5 (Flutter Application Foundations) are also complete (all 2026-08-09) — their own STATUS.md files are the detailed record; see `planning/current_phase.md` for the consolidated summary, since this file was not updated between Phase 2 and Phase 6 close-out and should not be treated as a phase-by-phase history for that gap.

---

# Repository Reality Check

**The foundation is built and verified, and Phase 6 delivered the first real business feature: Authentication.** No other business modules exist yet — no Customer, Order, Inventory, Delivery, Accounting aggregates, routes, or screens.

Note: the table and figures immediately below this line (`131 tests passing overall`, etc.) describe the repository as it stood at **Phase 2** close-out (2026-08-09) and were never updated through Phases 3–6, per this file's own precedence note at the top (`planning/current_phase.md` is authoritative when the two disagree). For current, phase-accurate figures see "Current Phase" above and [`planning/features/06-authentication-authorization/STATUS.md`](../planning/features/06-authentication-authorization/STATUS.md).

| Area | Status |
|---|---|
| `backend/` | FastAPI app, Clean Architecture layers, Unit of Work + illustrative repository/CQRS/domain-events, ARQ worker, Redis cache/idempotency/rate-limit infrastructure, audit foundation, 3 Alembic migrations applied to local DEV/UAT, 182 tests passing |
| `frontend/` | Nx workspace, Angular 22.0.8 dashboard, 36 tests passing |
| `mobile/` | Melos workspace, two app shells, three packages, 12 tests passing |
| `design-tokens/` | One JSON source → 229 CSS vars + TypeScript + Dart |
| `infrastructure/` | Docker Compose (PostgreSQL 17 + Redis 7) |
| `scripts/` | setup, dev-up/down, test, lint, format, check, tokens |
| `.github/workflows/` | 4 path-filtered validation workflows |
| `.gitignore` | Present, verified behaviourally |

**230 tests pass** (182 backend, up from 83 + 36 frontend + 12 Flutter), re-verified fresh — no cache to bypass for pytest; Nx cache explicitly bypassed for frontend. Lint, format, `mypy --strict`, and the five `import-linter` contracts all pass on the backend (80 files, 198 dependencies analyzed).

**Migrations exist for the first time.** `574dc291c82c` (citext/pg_trgm extensions), `0242df1a3871` (`tenant.tenant` + self-referential RLS — a tenant can see/rename only its own row, never another's, proven with real Tenant A/B rows against the actual `lpg_app` role), `40065f2b4dc3` (`audit.audit_log` + RLS + database-enforced immutability — `UPDATE`/`DELETE` denied to the application role at the grant level, not just by convention). Applied to local DEV, UAT, and the test database, and **now also applied to hosted Supabase PROD** (2026-08-09, DW-19/DW-20 — see below).

**Local database and Redis are fully verified** against real PostgreSQL 17 and Redis 7, with two per-environment application roles (`lpg_app`, `lpg_app_uat`) and the environment boundary enforced by revoking `PUBLIC`'s default `CONNECT`, not just documenting it.

**Live Supabase connection is now verified, and DW-19/DW-20 are resolved (2026-08-09).** `lpg_app` (`NOSUPERUSER`/`NOBYPASSRLS`) is provisioned directly on Supabase; the application connects as it, not `postgres`. `citext`/`pg_trgm` are installed. All three migrations applied via `alembic upgrade head` against the superuser migration URL; the migrations' own per-database grant-resolution logic applied `lpg_app`'s table privileges correctly with no changes needed. One incident along the way, self-corrected within the session: the local-dev pattern of revoking `PUBLIC`'s `CONNECT` (correct where dev/uat/test are separate databases) briefly broke Supabase's own Management API/MCP tooling, which shares the single `postgres` database without an explicit grant — caught immediately and reverted before any migration or application traffic was affected.

---

# Module Status

| Module | Status |
|----------|--------|
| Identity & Access | ✅ Authentication (Phase 6) + staff user-management CRUD (Phase 7) delivered |
| Administration / Tenant & Master Data | ✅ Complete (Phase 7) |
| Customer Management | ✅ Complete (Phase 8) |
| Driver Management | ✅ Complete (Phase 9) |
| Inventory Management | ✅ Complete (Phase 10) |
| Order Management | ✅ Complete (Phase 11) |
| Delivery & Dispatch | ✅ Complete (Phase 12) |
| Cylinder Ledger | ⏳ Planned |
| Accounting & Billing | ⏳ Planned |
| Complaint Management | ⏳ Planned |
| Notifications | ⏳ Planned |
| Reporting & Analytics | ⏳ Planned |

---

# Current Priorities

1. ~~Repository / Foundation~~ ✅ complete
2. ~~Backend Foundation~~ ✅ complete — Unit of Work, illustrative repository/CQRS/domain events, first 3 migrations with RLS, tenant-isolation suite, ARQ worker, audit/idempotency/rate-limit/cache infrastructure
3. ~~Shared Infrastructure~~ ✅ complete (2026-08-09) — `RedisRealtimePublisher` (ADR-015's port, now implemented) and `S3CompatibleFileStorage` over MinIO (D-40, ADR-030). WebSocket connection/subscription-authorization deliberately excluded — needs real Authentication (Phase 6); production object-storage vendor deliberately deferred with hosting topology (ADR-022).
4. ~~Angular Web Foundation completion~~ — ✅ **complete (Phase 4, 2026-08-09)**: brand palette refresh (ADR-031), collapsible-sidebar layout shell, Playwright e2e execution (T-34, closed after being blocked since Phase 1 — 27/27 tests passing), a WCAG 2.2 AA axe-core gate (found and fixed 3 real accessibility bugs), and the generated API client (ADR-032, `ng-openapi-gen`). Storybook is configured but its build is blocked on an Angular 22 / Storybook 10.5.x / Nx 23 ecosystem compatibility gap (DW-24, non-blocking). PrimeNG dependency install + token-theme wiring (T-68) and licence-tier eligibility (DW-22) were both closed earlier the same day, out of order, on explicit instruction.
5. ~~Flutter Application Foundations~~ — ✅ **complete (Phase 5, 2026-08-09)**: `DriftLocalDatabase`, a genuinely SQLCipher-encrypted Drift/SQLite implementation (ADR-034), wired into the Driver App only (ADR-008). Found and worked around a real ecosystem trap (`sqlcipher_flutter_libs` is now an EOL no-op; the current fix is `package:sqlite3`'s build-hook `source: sqlcipher` selection) and fixed a real resource-leak bug (a failed sanity-check query orphaning a background isolate's file lock). `api_client`, `auth`, and `sync_engine` packages remain not created — genuinely Phase 6 and Phase 11 scope, not this phase's (this line previously conflated them with Phase 5; corrected here).
6. ~~Authentication & Authorization~~ — ✅ **complete (Phase 6, 2026-08-10)**: replaces Phase 2's interim `HeaderTenantResolver` with a real `JwtTenantResolver` (same protocol, drop-in); closes DW-12 (tenant-scoped sessions now structurally mandatory); `api_client` and `auth` packages created and wired into both Flutter apps for the first time. Full detail: [`planning/features/06-authentication-authorization/STATUS.md`](../planning/features/06-authentication-authorization/STATUS.md).
7. ~~Administration & Tenant/Master Data~~ — ✅ **complete (Phase 7, 2026-08-10)**: Branch/Warehouse/Cylinder Type master data, historized Tenant Configuration and Price List, a full platform+tenant feature-flag system, staff user management (extends Identity), and a cursor-paginated audit-log read API — backend + Dashboard only. Full detail: [`planning/features/07-administration-tenant-master-data/STATUS.md`](../planning/features/07-administration-tenant-master-data/STATUS.md).
8. ~~Customer Management~~ — ✅ **complete (Phase 8, 2026-08-10)**.
9. ~~Driver Management~~ — ✅ **complete (Phase 9, 2026-08-10)**.
10. ~~Inventory Management~~ — ✅ **complete (Phase 10, 2026-08-11)**: `InventoryLocation` aggregate, GRN, load transfers, delivery/collection, status changes, adjustments, reconciliation. Full detail: [`planning/features/10-inventory-management/STATUS.md`](../planning/features/10-inventory-management/STATUS.md).
11. ~~Order Management~~ — ✅ **complete (Phase 11, 2026-08-12)**: 10-state `Order` aggregate, BR-04/BR-19 stub policy ports, Idempotency-Key-protected create/deliver, two-slice Angular UI. No dedicated `planning/features/11-order-management/` folder exists (a pre-existing gap — every other phase has one); full detail lives inline in `planning/current_phase.md`'s Current Phase section instead.
12. ~~Delivery & Dispatch~~ — ✅ **complete (Phase 12, 2026-08-13)**: `Route`/`RouteStop` replaces Order's interim `driver_id`/`vehicle_id`, reuses Inventory's load-transfer/reconciliation infrastructure rather than duplicating it, Dispatch Board rebuilt. Full detail: [`planning/features/12-delivery-dispatch/STATUS.md`](../planning/features/12-delivery-dispatch/STATUS.md).
13. **Cylinder Ledger (Phase 13)** — recommended next; now has a trustworthy Delivery bounded context under it.

Full dependency-ordered roadmap: [`docs/implementation/roadmap.md`](../docs/implementation/roadmap.md) and `planning/current_phase.md`.

---

# Architectural Decisions

All resolved. ADR-001 … ADR-026 in [`docs/architecture/15-architecture-decision-records.md`](../docs/architecture/15-architecture-decision-records.md).

**Confirmed in Phase 0 (2026-08-09):**

- Python 3.13 + FastAPI backend (ADR-012) — **supersedes the earlier ASP.NET Core direction**
- PostgreSQL over Azure SQL (ADR-013)
- Application services replace MediatR-style dispatch (ADR-014)
- FastAPI WebSockets + Redis Pub/Sub, real-time is Phase 1 scope (ADR-015)
- PostgreSQL RLS + repository scoping for tenant isolation (ADR-017)
- Angular 22 + Nx under `frontend/` (ADR-018)
- Signals-first with NgRx SignalStore (ADR-019)
- AG Grid Community (Enterprise optional per feature) behind an abstraction; PrimeNG as primary component library (ADR-020, amended by ADR-028)
- RFC 7807 error contract (ADR-021)
- Azure target cloud, hosting topology deferred (ADR-022)
- Background jobs: separate worker, Redis queue; library deferred (ADR-023)
- `import-linter` + `mypy --strict` boundary enforcement (ADR-024)
- Polyglot monorepo layout, `frontend/` not renamed (ADR-025)
- Code-first OpenAPI, generated spec committed as the client contract (ADR-026)

**Confirmed 2026-08-09 (post-Phase-1):**

- **Supabase as the managed PostgreSQL host only** (ADR-027) — amends ADR-013 (host named) and ADR-022 (database no longer maps to Azure). Supabase Auth, Storage, Realtime and Edge Functions are **not** adopted. Alembic remains the sole owner of schema; the application never connects as `service_role`.
- **Hybrid UI strategy** (ADR-028) — PrimeNG primary component library, AG Grid Community default (Enterprise optional per feature), amends ADR-020.
- **ARQ as the background job library** (ADR-029) — resolves ADR-023's deferral; async-native, Redis-backed, no second broker.
- **S3-compatible file storage port, MinIO for every environment that exists today** (ADR-030).
- **Brand colour moves from blue to deep forest green** (ADR-031).
- **`ng-openapi-gen` for the generated Angular API client** (ADR-032), with Angular `fileReplacements` for environment configuration (ADR-033, resolves 032's deferral).
- **SQLCipher-encrypted Drift via `package:sqlite3`'s build-hook source selection** (ADR-034), implementing `05-mobile-architecture.md` §7.

**Confirmed 2026-08-10 (Phase 6):**

- **JWT (RS256, `pyjwt[crypto]`) + Argon2id, with narrowly-scoped `SECURITY DEFINER` PostgreSQL functions resolving tenant before authentication** (ADR-035).
- **Shell-bypass routing for unauthenticated routes** (ADR-036) — a component-less parent route (`ShellLayout`), not a route-aware shell.
- **Hand-written Flutter `api_client` for Phase 6** (ADR-037) — spec-generation deferred, with an explicit revisit trigger once a comparably wide business-domain endpoint surface exists.

The superseded .NET architecture documents are preserved at [`docs/architecture/superseded/`](../docs/architecture/superseded/README.md) — historical only.

---

# Deferred Decisions

Deliberately open, each with a trigger point:

| Decision | Decide by |
|---|---|
| AG Grid Enterprise licence procurement (only if a feature needs it) | As triggered, no longer a standing blocker |
| PDF rendering library (WeasyPrint / ReportLab) | Printing phase |
| Azure **application** hosting topology + IaC tool (Bicep / Terraform) | Before production |
| Supabase production tier (lower tiers pause idle projects) | Before production |
| Production object-storage vendor (Azure Blob if Azure is chosen; ADR-030) | Before production, tied to hosting topology |
| KYC document types (pending business/legal) | Customer Management |
| Statutory backup retention duration | Production Hardening |
| Cancellation fee amount/configurability (D-19 residual) | ~~Order Management~~ resolved Phase 11 — tenant-configurable via `TenantConfiguration`'s `cancellation_fee_amount` key |

---

# Known Risks

- ~~The Supabase application role is not provisioned (DW-19)~~ — **resolved 2026-08-09.** `lpg_app` (`NOSUPERUSER`/`NOBYPASSRLS`) provisioned on Supabase; the application connects as it, not `postgres`.
- ~~`citext` and `pg_trgm` not installed on Supabase (DW-20)~~ — **resolved 2026-08-09.** Both installed via `alembic upgrade head` against Supabase.
- **`backend/.env` currently on disk is configured for PROD** (real Supabase host) — `LPG_DB_USER`/`LPG_DB_PASSWORD` now hold the `lpg_app` credential (not `postgres`), and `LPG_MIGRATION_DATABASE_URL` now holds the superuser DSN for Alembic. `LPG_REDIS_URL` is still empty. Importing `lpg.api.app` or `lpg.infrastructure.jobs.worker` directly (e.g. `uvicorn lpg.api.app:app`, `arq lpg.infrastructure.jobs.worker.WorkerSettings`) with this file as-is will crash at startup on a `pydantic` validation error over the missing Redis URL, not silently misconfigure.
- ~~Authentication not implemented~~ — **resolved 2026-08-10, Phase 6.** `JwtTenantResolver` now plugs into the `TenantResolver` protocol Phase 2 defined as the extension point; every module built from here on can assume a real, verified tenant/user context.
- ~~No tenant/master data existed~~ — **resolved 2026-08-10, Phase 7.** Branch, Warehouse, Cylinder Type, Tenant Configuration, Price List, and a full feature-flag system now exist; Customer Management (Phase 8) and Inventory (Phase 9) can foreign-key against them.
- Unit of Work, one illustrative repository/CQRS use case, and the domain-event dispatcher are now implemented (Phase 2) — no business aggregate, repository, or router beyond Identity (Phase 6) and Administration/master data (Phase 7) exists yet.
- AG Grid runs on **Community** — this is now the confirmed platform default (ADR-028), not a discrepancy against ADR-020 as it was previously recorded. Enterprise remains available per feature; the wrapper (ADR-020) keeps enabling it a two-line change rather than a refactor. **PrimeNG is installed, token-wired, and licence-eligible** (T-68 and DW-22, both 2026-08-09, both brought forward from Phase 4 to Phase 1 close-out on explicit instruction).
- ~~`mobile/packages/api_client`, `auth` and `sync_engine` are documented but not created~~ — **`api_client` and `auth` created and wired into both apps, 2026-08-10, Phase 6.** `sync_engine` remains not created; still genuinely Phase 11 scope (offline sync queue, per `local_storage`'s own doc comment).
- **Mobile SQLCipher build hook not yet confirmed on CI.** `mobile/packages/local_storage`'s `DriftLocalDatabase` (Phase 5, ADR-034) uses `package:sqlite3`'s `hooks.user_defines.sqlite3.source: sqlcipher` build-hook mechanism, verified locally (Windows, `flutter 3.44.2`) with real encryption round-trip and wrong-key-failure tests, but not yet observed passing on the actual `ubuntu-latest` runner `.github/workflows/mobile-ci.yml` uses. Remove this line once the next CI run of a `mobile/**` change confirms it green.
- `docs/modules/` per-module specifications referenced by several documents **do not exist**; equivalent content is distributed across `docs/srs/`, `docs/business/`, `docs/engineering/`, and `docs/data/` (see [`docs/README.md`](../docs/README.md)).
- **DW-24 — Storybook's build fails** (`nx build-storybook shared-ui`, error `SB_BUILDER-WEBPACK5_0003`), a chain of Angular 22 / Storybook 10.5.x / Nx 23.1.1 ecosystem compatibility gaps, not yet fully root-caused. Configuration and stories (`libs/shared/ui/.storybook/`, `app-shell.component.stories.ts`, `data-grid.component.stories.ts`) are real and correct. **Explicitly deferred to post-MVP by product owner decision (2026-08-09)** — not revisited until after MVP. See `planning/features/04-angular-web-foundation/STATUS.md`.
- The generated API client (`libs/shared/data-access/src/lib/generated/`, ADR-032) is now wired into `app.config.ts` via `provideApiConfiguration(environment.apiUrl)` (ADR-033, 2026-08-09), backed by a new `fileReplacements`-based frontend environment-config pattern (`apps/dashboard/src/environments/`). Still only has the two health endpoints to call until a real business API surface exists.

No critical business risks identified.

---

# AI Instructions

Before beginning work:

1. Read `planning/current_phase.md` — it is authoritative on what is happening now.
2. Read this file for the summary view.
3. Confirm the requested feature has not already been implemented.
4. Review `knowledge/10-feature-map.md` for dependencies.
5. Read the relevant business and architecture documentation.
6. Follow `AGENTS.md` and the engineering standards.
7. Update this file after completing a major milestone.

Never:

- Re-implement completed features.
- Skip planned dependencies.
- Change architecture without an ADR.
- Implement from anything in `docs/architecture/superseded/`.

---

# Change Log

| Date | Version | Description |
|------|---------|-------------|
| 2026-08-13 | 1.14 | Post-completion, cross-cutting UI fix pass (user-reported from live use, not a new phase), now fully closed: Order Detail header overlap fixed, the Deliver drawer's "Amount Collected" currency input replaced (was a masked field with a real editing bug — typed digits inserted into the mask instead of replacing it), checkbox-driven row selection on the Orders/Customers/Drivers/Vehicles grids replaced with a new reusable link-cell capability on the shared `DataGridComponent`, shell/page-header responsiveness fixed (including a real flexbox bug letting wide content push the whole page into horizontal scroll). Also found and closed a genuine, previously-undiscovered, **app-wide** bug: the installed PrimeNG v22's `[pButton]` directive silently dropped its `icon`/`label` inputs (v21+), so every icon-bearing `pButton` anywhere in the app — across every phase that used it — was rendering with no icon; `<p-button>` the component is unaffected. Fixed in 18 files total (3 live-verified directly, 15 more — 36 button instances — via a background sweep), independently re-verified with a fresh build (zero errors) and fresh lint (8/9 clean; the 9th fails only on an unrelated pre-existing boundary violation, see below). See `planning/features/12-delivery-dispatch/STATUS.md`'s "Post-completion UI fixes" section. **Unrelated finding**: a new, untracked `frontend/libs/ledger/feature-ledger/` appeared mid-session — a separate, concurrent session appears to be starting Phase 13 (Cylinder Ledger) independently of this conversation; it has already wired a `FeatureLedger` import into `feature-customers.ts` (tripping an Nx module-boundary lint rule). Not touched here; flagged in `planning/current_phase.md` so it isn't mistaken for a regression. |
| 2026-08-13 | 1.13 | Phase 12 (Delivery & Dispatch) complete, verified independently rather than self-reported: `Route`/`RouteStop` replaces `Order`'s interim `driver_id`/`vehicle_id` (dropped) with `route_stop_id`; `VehicleLoadEvent`/`VehicleShiftReconciliation` deliberately descoped in favor of reusing Inventory Management's load-transfer/reconciliation infrastructure (`docs/data/01-domain-model.md` §4.4 divergence note); Dispatch Board rebuilt from a list+create stub into a real operational screen. An independent audit on 2026-08-12 had caught a false "complete" claim (zero tests, broken `import-linter`, most of the frontend missing) — every gap is now closed: 486 unit tests + 39 Phase-12-scope integration tests re-run by hand, static gates re-run by hand, and a live-browser pass through the real stack (route auto-complete and reconcile-409-gating both confirmed live, not just in code). Two further real bugs found and fixed while writing tests: Route's domain events were silently never dispatched, and nothing ever transitioned a route to `completed`. |
| 2026-08-12 | 1.12 | Phase 11 (Order Management) complete: 10-state `Order` aggregate (`draft` → ... → `closed`, plus `failed_delivery`/`cancelled` branches), BR-04/BR-19 stub policy ports (`CylinderCapPolicy`/`CreditLimitEvaluator`), tenant-configurable cancellation fee reusing Phase 7's `TenantConfiguration` resolver, Idempotency-Key-protected `POST /orders`/`POST /orders/{id}/deliver`, two-slice Angular UI (Order Queue/detail/create, then the full dispatch-pipeline of action drawers). `assign` wrote raw `driver_id`/`vehicle_id` onto `Order` as a deliberate, documented interim step — replaced by Phase 12's real `Route`/`RouteStop` relationship. |
| 2026-08-11 | 1.11 | Phase 10 (Inventory Management) complete: `InventoryLocation` aggregate (warehouse/vehicle balances by cylinder type × status), `inventory` PostgreSQL schema (5 tables, RLS), RBAC permissions (`inventory:read`, `inventory:load`, `inventory:adjust`, `reconciliation:approve` — the last live-checked), GRN, load transfers, delivery/collection, status changes, adjustments, reconciliation, OpenAPI client, lazy-loaded `@lpg/inventory/feature-inventory` UI. 511 backend tests passing (up from 455), `mypy --strict`/`import-linter` 5/5/`ruff` all clean, live-verified end to end in the browser. Three real defects found and fixed via independent database verification (duplicate permission seeding, a repository duplicate-row/FK-ordering bug, a missing `Computed()` marker on a generated column). |
| 2026-08-10 | 1.10 | Phase 9 (Driver Management) complete: delivered `Driver` and `Vehicle` aggregate roots, `delivery` PostgreSQL schema, RLS policies, RBAC permissions (`drivers:read`, `drivers:manage`, `vehicles:read`, `vehicles:manage`), application use cases, OpenAPI spec client, lazy-loaded Angular UI components (`@lpg/delivery/feature-drivers` and `@lpg/delivery/feature-vehicles`), wired routes and navigation items. All quality gates pass (`mypy --strict`, `import-linter` 5/5, 252 backend unit tests + 10 integration tests, 13/13 frontend project test suites, production build 100% successful). |
| 2026-08-10 | 1.9 | Phase 8 (Customer Management) complete. |
| 2026-08-10 | 1.8 | Phase 7 (Administration & Tenant/Master Data) complete. |
| 2026-08-10 | 1.7 | Phase 6 (Authentication & Authorization) complete: hand-built Identity module across all three stacks — JWT (RS256, `pyjwt[crypto]`) + Argon2id, OTP login, RBAC, password reset, `SECURITY DEFINER`-based tenant resolution before auth (ADR-035); shell-bypass routing (ADR-036); new mobile `api_client`/`auth` packages (ADR-037). Closes DW-12. 359 tests passing (259 backend + 56 frontend + 44 mobile). This entry also catches up the gap left by Phases 3–5 (Shared Infrastructure, Angular Web Foundation, Flutter Application Foundations — all complete 2026-08-09, each with its own `planning/features/0{3,4,5}-*/STATUS.md`) not having been logged here individually; `planning/current_phase.md` remained the authoritative, current-throughout record for that gap, per this file's own stated precedence rule. |
| 2026-08-09 | 1.6 | Phase 2 (Backend Foundation) complete: Unit of Work, illustrative repository/CQRS/domain-event seam (`Tenant`/`RenameTenantUseCase`), 3 Alembic migrations (extensions, `tenant.tenant`+RLS, `audit.audit_log`+RLS+DB-enforced immutability) applied to local DEV/UAT, dedicated `tests/tenant_isolation/` suite, ARQ background-worker foundation (ADR-029), Redis cache/idempotency/rate-limit infrastructure, an observability gap closed (tenant_id/user_id now bind to structured logs). 182 backend tests (up from 83), 230 total. |
| 2026-08-09 | 1.5 | Frontend component-library architecture revised: hybrid UI strategy adopted (ADR-028, amends ADR-020) — PrimeNG restored as primary component library, AG Grid Community made the default data-grid engine with Enterprise now optional per feature. A hardcoded PrimeNG licence key found and removed from `app.config.ts` before it reached git history. |
| 2026-08-09 | 1.4 | Phase 1 re-verified fresh: live Supabase connection confirmed (found rolbypassrls=True on `postgres`, citext/pg_trgm missing), dev/uat password rotation verified from host, dotenv-hermeticity bug in tests fixed, 22 tests added closing a zero-coverage gap in two shared libraries. 131 tests total. |
| 2026-08-09 | 1.3 | Phase 1 closed out: Docker verifications completed, tenant-context bug found and fixed, Supabase config added, architecture-consistency checker introduced |
| 2026-08-09 | 1.2 | Phase 1 complete: all three stacks scaffolded and verified; 75 tests passing; boundary enforcement live; first commit made |
| 2026-08-09 | 1.1 | Phase 0 complete: .NET architecture superseded, Python/FastAPI architecture documented, ADR-012…026 added, status corrected to reflect an empty repository |
| — | 1.0 | Initial knowledge base created |

---

# Related Documentation

- [`planning/current_phase.md`](../planning/current_phase.md) — **authoritative current state**
- [`AGENTS.md`](../AGENTS.md)
- [`docs/README.md`](../docs/README.md) — documentation index and legacy path map
- [`docs/implementation/roadmap.md`](../docs/implementation/roadmap.md)
