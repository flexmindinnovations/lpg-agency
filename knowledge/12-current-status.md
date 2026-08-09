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
| Web Dashboard | Angular 22 in an Nx workspace (`frontend/`), Signals + NgRx SignalStore, Angular Material + CDK, Tailwind CSS v4, AG Grid Enterprise |
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
| Backend Development | 🔨 Foundation only — no business features |
| Frontend Development | 🔨 Foundation only — no business features |
| Mobile Development | 🔨 Shells only — no business features |
| Testing | 🔨 Harness in place — 75 foundation tests pass |
| Deployment | 🔨 CI validation only — no deployment pipelines |

---

# Current Phase

**Completed:** Phase 1 — Repository / Development Foundation

**Next:** Phase 2 — Backend Foundation (**not started**; requires explicit go-ahead)

Phase 2 scope: Unit of Work, base repository, domain-event dispatcher, first Alembic migration with RLS policies, tenant-isolation test suite, background worker, real-time publisher. Still no business features.

---

# Repository Reality Check

**The foundation is built and verified. There are still no business features** — no authentication, no domain aggregates, no business routes or screens.

| Area | Status |
|---|---|
| `backend/` | FastAPI app, Clean Architecture layers, live-verified Supabase config, 83 tests passing |
| `frontend/` | Nx workspace, Angular 22.0.8 dashboard, 14 tests passing |
| `mobile/` | Melos workspace, two app shells, three packages, 12 tests passing |
| `design-tokens/` | One JSON source → 229 CSS vars + TypeScript + Dart |
| `infrastructure/` | Docker Compose (PostgreSQL 17 + Redis 7) |
| `scripts/` | setup, dev-up/down, test, lint, format, check, tokens |
| `.github/workflows/` | 4 path-filtered validation workflows |
| `.gitignore` | Present, verified behaviourally |
| Git commits | `470436e` — 428 files, working tree clean |

**131 tests pass** (83 backend + 36 frontend + 12 Flutter), re-verified fresh with caches bypassed. Lint, format, `mypy --strict`, and the five `import-linter` contracts all pass.

**Local database and Redis are fully verified** against real PostgreSQL 17 and Redis 7, with two per-environment application roles (`lpg_app`, `lpg_app_uat`) and the environment boundary enforced by revoking `PUBLIC`'s default `CONNECT`, not just documenting it.

**Live Supabase connection is now verified** — password supplied, connection made via the application's real connection-composition code and independently via Alembic. Found: `postgres` on Supabase has `rolbypassrls=True` (DW-19, provisioning a safe role is the next step); `citext`/`pg_trgm` are not yet installed there (DW-20).

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
2. **Backend Foundation** — Unit of Work, base repository, domain events, first migration with RLS, tenant-isolation suite, background worker, real-time publisher
3. **Shared Infrastructure** — audit logging, idempotency store, caching, rate limiting, file storage
4. **Angular Web Foundation completion** — Storybook, Playwright execution, AG Grid Enterprise licence
5. **Flutter Foundation completion** — `api_client`, `auth`, `sync_engine` packages
6. **Authentication & Authorization**

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
- AG Grid Enterprise behind an abstraction (ADR-020)
- RFC 7807 error contract (ADR-021)
- Azure target cloud, hosting topology deferred (ADR-022)
- Background jobs: separate worker, Redis queue; library deferred (ADR-023)
- `import-linter` + `mypy --strict` boundary enforcement (ADR-024)
- Polyglot monorepo layout, `frontend/` not renamed (ADR-025)
- Code-first OpenAPI, generated spec committed as the client contract (ADR-026)

**Confirmed 2026-08-09 (post-Phase-1):**

- **Supabase as the managed PostgreSQL host only** (ADR-027) — amends ADR-013 (host named) and ADR-022 (database no longer maps to Azure). Supabase Auth, Storage, Realtime and Edge Functions are **not** adopted. Alembic remains the sole owner of schema; the application never connects as `service_role`.

The superseded .NET architecture documents are preserved at [`docs/architecture/superseded/`](../docs/architecture/superseded/README.md) — historical only.

---

# Deferred Decisions

Deliberately open, each with a trigger point:

| Decision | Decide by |
|---|---|
| Background job library (ARQ / Dramatiq / Celery) | Backend Foundation |
| AG Grid Enterprise licence procurement | Angular Foundation |
| PDF rendering library (WeasyPrint / ReportLab) | Printing phase |
| Azure **application** hosting topology + IaC tool (Bicep / Terraform) | Before production |
| Supabase production tier (lower tiers pause idle projects) | Before production |
| KYC document types (pending business/legal) | Customer Management |
| Statutory backup retention duration | Production Hardening |
| Inventory counter granularity (D-04/D-14 residual) | Inventory Management |
| Cancellation fee amount/configurability (D-19 residual) | Order Management |
| Warehouse Staff vs Warehouse Manager (D-38 residual) | Authentication & Authorization |

---

# Known Risks

- **The Supabase application role is not provisioned** (DW-19) — the live connection currently verified uses `postgres`, which has `rolbypassrls=True`. Must not be the application's own connection. Role creation is administrative, not schema, so it cannot go through Alembic.
- **`citext` and `pg_trgm` not installed on Supabase** (DW-20) — only `pgcrypto` is, confirmed live.
- Authentication not implemented — every module depends on it.
- No database migrations yet; the first arrives in Phase 2 with the `tenant` schema and its RLS policies.
- Unit of Work, repositories and the domain-event dispatcher are designed but not implemented.
- AG Grid runs on **Community**, not Enterprise — licence procurement unconfirmed. The wrapper (ADR-020) keeps this a two-line change rather than a refactor.
- `mobile/packages/api_client`, `auth` and `sync_engine` are documented but not created; they have no content until Phase 6 and Phase 11.
- `docs/modules/` per-module specifications referenced by several documents **do not exist**; equivalent content is distributed across `docs/srs/`, `docs/business/`, `docs/engineering/`, and `docs/data/` (see [`docs/README.md`](../docs/README.md)).

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
