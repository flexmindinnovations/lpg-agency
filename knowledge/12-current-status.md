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
| Architecture Decision Records | ✅ Complete (ADR-001 … ADR-026) |
| Data Architecture | ✅ Complete |
| API Contracts | ✅ Complete |
| UX Architecture | ✅ Complete |
| Design System | ✅ Complete |
| Engineering Standards | ✅ Complete |
| **Documentation Reconciliation (Phase 0)** | ✅ **Complete — 2026-08-09** |
| **Repository / Development Foundation (Phase 1)** | ✅ **Complete — 2026-08-09** |
| **Backend Foundation (Phase 2)** | ✅ **Complete — 2026-08-09** |
| Backend Development | 🔨 Foundation + reusable infrastructure only — no business features |
| Frontend Development | 🔨 Foundation only — no business features |
| Mobile Development | 🔨 Shells only — no business features |
| Testing | 🔨 Harness in place — **230 foundation tests pass** (182 backend, up from 83; 36 frontend; 12 Flutter) |
| Deployment | 🔨 CI validation only — no deployment pipelines |

---

# Current Phase

**Completed:** Phase 2 — Backend Foundation (2026-08-09)

**Next:** Phase 3 — Shared Infrastructure, or Phase 4 — Angular Web Foundation (**not started**; requires explicit go-ahead). Recommendation: Phase 6 (Authentication) is the more natural next dependency — the interim `HeaderTenantResolver` (Phase 2) and the not-yet-mandatory-unscoped-session seam (DW-12) both exist specifically to be replaced by it.

Phase 2 delivered: Unit of Work (`SqlAlchemyUnitOfWork`), one illustrative repository + CQRS use case (`Tenant`/`RenameTenantUseCase`, not a business feature), in-process domain-event dispatcher, the first three Alembic migrations (`citext`/`pg_trgm` extensions, `tenant.tenant` + self-referential RLS, `audit.audit_log` + RLS with database-enforced immutability), a dedicated tenant-isolation test suite (two seeded tenants, RLS proven directly against the app role, not through application filters), the background worker (ARQ, ADR-029) with a trivial round-trip-proof job, Redis cache/idempotency/rate-limit infrastructure, and an observability gap closed (tenant_id/user_id now bind to structured logs). Still no business features — no authentication, no domain aggregates beyond the RLS-proof `Tenant`, no business routes.

---

# Repository Reality Check

**The foundation is built and verified. There are still no business features** — no authentication, no domain aggregates, no business routes or screens.

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
| Identity & Access | ⏳ Planned |
| Administration / Tenant & Master Data | ⏳ Planned |
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
6. **Authentication & Authorization** — replaces Phase 2's interim `HeaderTenantResolver` with a real `JwtTenantResolver` (same protocol, drop-in); closes DW-12 (mandatory tenant-scoped session); first real consumer of the `api_client` package and the Flutter apps' `auth` package

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
| Warehouse Staff vs Warehouse Manager (D-38 residual) | Authentication & Authorization |

---

# Known Risks

- ~~The Supabase application role is not provisioned (DW-19)~~ — **resolved 2026-08-09.** `lpg_app` (`NOSUPERUSER`/`NOBYPASSRLS`) provisioned on Supabase; the application connects as it, not `postgres`.
- ~~`citext` and `pg_trgm` not installed on Supabase (DW-20)~~ — **resolved 2026-08-09.** Both installed via `alembic upgrade head` against Supabase.
- **`backend/.env` currently on disk is configured for PROD** (real Supabase host) — `LPG_DB_USER`/`LPG_DB_PASSWORD` now hold the `lpg_app` credential (not `postgres`), and `LPG_MIGRATION_DATABASE_URL` now holds the superuser DSN for Alembic. `LPG_REDIS_URL` is still empty. Importing `lpg.api.app` or `lpg.infrastructure.jobs.worker` directly (e.g. `uvicorn lpg.api.app:app`, `arq lpg.infrastructure.jobs.worker.WorkerSettings`) with this file as-is will crash at startup on a `pydantic` validation error over the missing Redis URL, not silently misconfigure.
- Authentication not implemented — every module depends on it. Phase 2 added the extension point (`TenantResolver` protocol) it will plug into.
- Unit of Work, one illustrative repository/CQRS use case, and the domain-event dispatcher are now implemented (Phase 2) — no business aggregate, repository, or router exists yet.
- AG Grid runs on **Community** — this is now the confirmed platform default (ADR-028), not a discrepancy against ADR-020 as it was previously recorded. Enterprise remains available per feature; the wrapper (ADR-020) keeps enabling it a two-line change rather than a refactor. **PrimeNG is installed, token-wired, and licence-eligible** (T-68 and DW-22, both 2026-08-09, both brought forward from Phase 4 to Phase 1 close-out on explicit instruction).
- `mobile/packages/api_client`, `auth` and `sync_engine` are documented but not created; they have no content until Phase 6 and Phase 11.
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
