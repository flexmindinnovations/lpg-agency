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
| Backend Development | 🔨 Identity (Phase 6) + Administration/master-data (Phase 7) delivered — no other business features yet |
| Frontend Development | 🔨 Auth UI (Phase 6) + Administration UI (Phase 7) delivered — no other business features yet |
| Mobile Development | 🔨 Auth wired into both apps (Phase 6) — Administration is Dashboard-only, no mobile work in Phase 7 |
| Testing | 🔨 Harness in place — **425 tests pass** (369 backend + 56 frontend across 6 tested Nx projects) at Phase 7 close-out; mobile unchanged at 44 (Administration had no mobile scope) — see [`planning/features/07-administration-tenant-master-data/STATUS.md`](../planning/features/07-administration-tenant-master-data/STATUS.md) |
| Deployment | 🔨 CI validation only — no deployment pipelines |

---

# Current Phase

**Completed:** Phase 7 — Administration & Tenant/Master Data (2026-08-10)

**Next:** Phase 8 — Customer Management (**not started**; requires explicit go-ahead). WebSocket connection/subscription authorization (excluded from Phase 3's `RealtimePublisher`) remains tracked as its own immediate fast-follow, not bundled into a later numbered phase.

Phase 7 delivered master data for tenants to configure and a way to administer their own staff, across the backend and the Dashboard only (no mobile scope): Branch, Warehouse, Cylinder Type (standard tenant-scoped RLS master data), historized Tenant Configuration and Price List (each resolved at a point in time by its own domain service — `TenantConfigurationResolver`/`EffectivePriceResolver`), a full platform+tenant feature-flag system (percentage rollout, scheduling — the larger, non-recommended option the user explicitly chose over a simple per-tenant boolean table), staff user management (extends the existing Identity bounded context rather than a new indirection layer, per explicit user choice), and a cursor-paginated audit-log read API. A documented divergence from `01-domain-model.md` §4.1: Branch/Warehouse/TenantConfiguration/CylinderType/PriceListEntry became independent aggregate roots rather than entities nested inside `Tenant` — loading the whole Tenant graph to edit one branch was impractical. 369 backend tests passing (up from 259), 56 frontend tests (unchanged — the new admin libs have no dedicated component tests). Seven genuine, previously-latent bugs found and fixed along the way, including a pre-existing double `/api/v1` URL prefix affecting the whole app's API calls and an AG Grid 0px-height rendering bug across all 8 new admin pages (both found only because this phase's manual browser verification was the first real end-to-end check of these paths). Full detail: [`planning/features/07-administration-tenant-master-data/STATUS.md`](../planning/features/07-administration-tenant-master-data/STATUS.md).

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
| Customer Management | ⏳ Planned |
| Inventory Management | ⏳ Planned |
| Order Management | ⏳ Planned |
| Delivery Management | ⏳ Planned |
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
8. **Customer Management (Phase 8)** — recommended next; the roadmap's next dependency now that Administration's master data exists for it to foreign-key against.

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
| Inventory counter granularity (D-04/D-14 residual) | Inventory Management |
| Cancellation fee amount/configurability (D-19 residual) | Order Management |

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
| 2026-08-10 | 1.8 | Phase 7 (Administration & Tenant/Master Data) complete: Branch/Warehouse/Cylinder Type master data, historized Tenant Configuration and Price List (each with its own point-in-time resolver domain service), a full platform+tenant feature-flag system (percentage rollout, scheduling), staff user management (extends Identity), cursor-paginated audit-log read API — backend + Dashboard only, no mobile scope. A documented divergence from `01-domain-model.md` §4.1: Branch/Warehouse/TenantConfiguration/CylinderType/PriceListEntry are now independent aggregate roots, not entities nested inside `Tenant`. 369 backend tests (up from 259), 56 frontend tests (unchanged). Seven genuine, previously-latent bugs found and fixed, including a pre-existing double `/api/v1` URL prefix and an AG Grid 0px-height rendering bug across all 8 new admin pages. |
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
