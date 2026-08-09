# Current Development Phase

## Project

LPG Agency Management Platform

---

## Current Phase

**Phase 1 — Repository / Development Foundation** ✅ **COMPLETE** (5 verifications environment-blocked)

**Next phase — Phase 2: Backend Foundation — NOT STARTED.** It requires an explicit go-ahead.

Phase 0 — Documentation Reconciliation & Technical Baseline — is also complete; see [`planning/features/00-documentation-reconciliation/STATUS.md`](./features/00-documentation-reconciliation/STATUS.md).

---

## Phase Objective

**Phase 1 (complete):** establish the production-ready repository structure and developer tooling for the Angular 22, FastAPI, Flutter, PostgreSQL and Redis applications — foundation only, no business functionality.

Achieved. A developer can clone, run one setup command, and every application starts, every test suite runs, and every quality gate passes — with no business logic present.

---

## Current Repository State

Verified 2026-08-09, post-Phase-1. Every figure below came from running a command.

**The repository now contains working, verified code — and still no business features.** No authentication, no domain aggregates, no business routes or screens. That is deliberate; each arrives in its own phase.

### Built and verified

| Area | State |
|---|---|
| **Backend** (`backend/`) | FastAPI app on Python 3.13.5. Clean Architecture layers, Pydantic settings with production guard rails, structlog with central redaction, correlation IDs, RFC 7807 errors, async SQLAlchemy with the RLS tenant seam, Redis client, split liveness/readiness probes, Alembic harness, committed + drift-checked OpenAPI spec. **49 tests pass.** |
| **Frontend** (`frontend/`) | Nx 23.1.1 workspace, **Angular 22.0.8** dashboard. Design tokens, three themes, four shared libraries, AG Grid behind a wrapper, RFC 7807 + correlation interceptors, accessible app shell. **14 tests pass.** |
| **Mobile** (`mobile/`) | Melos workspace: `customer_app`, `driver_app`, and `core`/`design_system`/`local_storage` packages. Riverpod, go_router, generated Dart tokens with three themes. **12 tests pass.** |
| **Design tokens** (`design-tokens/`) | One JSON source generating 229 CSS variables, TypeScript constants and Dart constants. Drift-checked in CI. |
| **Local environment** (`infrastructure/`) | Docker Compose: PostgreSQL 17 + Redis 7, non-default ports, healthchecks, init SQL creating the `NOBYPASSRLS` application role. |
| **Scripts** (`scripts/`) | setup, dev-up, dev-down, test, lint, format, check, generate-tokens. |
| **CI** (`.github/workflows/`) | Four path-filtered workflows; validation only, no deployment. |
| **Git** | First commit `470436e`, 428 files, working tree clean. |

**75 tests passing overall.** Lint, format, type check and boundary contracts pass on all three stacks.

### Enforcement that is live

Not conventions — these fail the build:

| Rule | Mechanism | Status |
|---|---|---|
| Clean Architecture dependency direction | `import-linter`, 5 contracts | ✅ 5 kept, 0 broken |
| Full type coverage at boundaries | `mypy --strict` | ✅ 36 files clean |
| Feature libraries never import each other | Nx `enforce-module-boundaries` | ✅ 6 projects clean |
| Design tokens match their single source | Generator `--check` | ✅ |
| OpenAPI spec matches implementation | Export `--check` | ✅ |
| No environment file committed | Repository CI | ✅ |
| Superseded .NET architecture stays superseded | Repository CI | ✅ |

The boundary contracts earned their place on first run: they caught the API layer importing `Database` directly. Fixed properly by depending on the application-layer `HealthCheck` port, with the composition root carrying a declared exception.

### Not started

Authentication · RBAC · every business module · background worker · real-time WebSocket implementation · printing engine · production infrastructure · deployment pipelines · offline sync.

### Environment-blocked verifications

**Docker Desktop's daemon would not start here.** Five verifications could not be executed and are marked blocked, not complete: container startup (T-08), live database connection (T-15), live Redis connection (T-16), `alembic current` against a live database (T-19), and Playwright e2e execution (T-34, needs browser binaries).

Configuration is authored and validated — `docker compose config` parses, and the readiness endpoint correctly reports both dependencies unreachable with per-dependency detail. One command closes these out on a machine with working Docker:

```bash
./scripts/dev-up.sh && ./scripts/check.sh
```

---

## Technology Baseline

Confirmed by the product owner on 2026-08-09. Recorded as ADR-012 … ADR-026.

| Layer | Technology |
|---|---|
| Backend | Python 3.13+, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2 |
| Database | PostgreSQL on **Supabase** (managed host only, ADR-027), with Row-Level Security tenant isolation |
| Cache / queue / real-time backplane | Redis |
| Web dashboard | Angular 22, strict TypeScript, **Nx** workspace at `frontend/`, Signals + NgRx SignalStore, Angular Material + CDK, Tailwind CSS v4, **AG Grid Enterprise** (behind a wrapper), Storybook, Jest, Playwright |
| Mobile | Flutter, Riverpod, Drift SQLite; Driver App offline-first |
| Real-time | FastAPI WebSockets + Redis Pub/Sub — **Phase 1 scope** |
| Boundary enforcement | `import-linter`, `mypy --strict` (backend); Nx `enforce-module-boundaries` (frontend) |
| Container / CI / cloud | Docker, GitHub Actions, Azure |

**Discrepancies: none remaining.** All eight identified in the initial assessment are resolved:

| # | Was | Resolved |
|---|---|---|
| D1 | .NET vs Python backend | Python/FastAPI — ADR-012; .NET preserved under `superseded/` |
| D2 | Angular 20 vs 22; Nx unconfirmed | Angular 22 + Nx at `frontend/` — ADR-018 |
| D3 | Three conflicting state-management positions | Ordered Signals-first rule set — ADR-019 |
| D4 | AG Grid vs Material/PrimeNG | AG Grid Enterprise behind an abstraction; PrimeNG dropped — ADR-020 |
| D5 | `{success, error}` vs RFC 7807 | RFC 7807 + `error_code` — ADR-021 |
| D6 | "OpenAPI first" vs "code-first" | Code-first generation, generated spec committed as the client contract — ADR-026 |
| D7 | Azure SignalR, no FastAPI equivalent | FastAPI WebSockets + Redis Pub/Sub — ADR-015 |
| D8 | Azure topology assumed a .NET/SQL stack | Azure confirmed; topology and IaC tool deliberately deferred — ADR-022 |

---

## Architecture Baseline

**Documented, and now partly realised.** The foundation layers below exist in code and are enforced by CI. The business layers above them do not exist yet.

### Documented, with foundation implemented

- **Clean Architecture** — Domain → Application → Infrastructure → API, dependency rule pointing inward, enforced in CI by `import-linter` and `mypy --strict` (`docs/architecture/03-backend-architecture.md`)
- **DDD** — aggregates with single roots, domain events dispatched **after** commit, bounded contexts matching both backend module folders and PostgreSQL schema names
- **Modular monolith** with documented extraction seams (ADR-002)
- **CQRS in-process via explicit application services** — no mediator library; the five former MediatR behaviors re-expressed as FastAPI dependencies and Unit of Work responsibilities (ADR-014)
- **Repository per aggregate root + Unit of Work** — one transaction per command, guaranteeing BR-29
- **Tenant isolation, four layers** — PostgreSQL RLS, `SET LOCAL app.current_tenant_id`, repository scoping, CI tests (ADR-017)
- **REST + WebSockets** — `/api/v1`, RFC 7807 errors, `snake_case` JSON, idempotency keys, optimistic concurrency
- **Real-time** — transport-agnostic publisher port, tenant-namespaced channels, RBAC-authorized subscriptions, at-most-once delivery with REST as the source of truth
- **Background jobs** — separate worker process, jobs as use cases, always tenant-scoped, idempotent
- **Printing** — server-side, block-based, tenant-configurable, renderer-agnostic
- **Frontend** — Nx feature libraries that cannot import each other, Signals-first state, design tokens, AG Grid behind a wrapper, WCAG 2.2 AA
- **Testing** — six layers, with tenant isolation as its own suite and boundary contracts as merge-blocking CI checks

### Gaps closed

**Phase 0** closed all nine documentation gaps (A1–A9): folder structure reconciled, docs sub-structure mapped, Python backend layering authored, the MediatR-equivalent designed, tenant isolation unified on PostgreSQL RLS, printing rebound to Python, real-time designed, background jobs designed, boundary enforcement specified.

**Phase 1** turned the load-bearing parts of that into running, enforced code: the layer structure exists and `import-linter` guards it; the RFC 7807 contract is implemented and tested; the RLS tenant seam is wired; the design-token pipeline generates all three platforms from one source; the OpenAPI contract is committed and drift-checked.

Still documentation-only, by design: the Unit of Work, repositories, domain-event dispatcher, background worker, real-time publisher implementation, and printing engine. Each arrives with the phase that needs it.

---

## Documentation Baseline

### Changed in Phase 0

**Preserved (moved, banner added):** `superseded/01-system-architecture-dotnet.md`, `03-backend-architecture-dotnet.md`, `06-database-architecture-dotnet.md`, `09-printing-architecture-dotnet.md`, `13-deployment-dotnet.md`, `14-folder-structure-dotnet.md`, plus `superseded/README.md`.

**Rewritten:** `01-system-architecture.md`, `03-backend-architecture.md`, `04-frontend-architecture.md`, `06-database-architecture.md`, `09-printing-architecture.md`, `13-deployment.md`, `14-folder-structure.md`, `15-architecture-decision-records.md`.

**Created:** `16-realtime-architecture.md`, `docs/README.md`, `docs/adr/README.md`, `docs/implementation/roadmap.md`, `docs/implementation/module-implementation-plan.md`.

**Corrected in place:** `02-domain-driven-design.md`, `07-api-architecture.md`, `08-security-architecture.md`, `10-performance-strategy.md`, `12-observability.md`, `docs/implementation/README.md`, `engineering-standards.md`, `testing-strategy.md`, `docs/adr/decisions.md`, `docs/business/assumptions.md`, `docs/engineering/open-questions.md`, all `knowledge/` summaries, `AGENTS.md`, `README.md`.

### Remaining documentation gaps

1. **`docs/modules/` does not exist** — see Current Repository State above. Consolidation before each module's implementation phase would be worthwhile.
2. **`docs/LPG_Agency_Management_System_Blueprint.pdf` has never been read by an agent.** All markdown is derived from it and is stakeholder-approved; re-deriving from source is a separate verification exercise (DW-01).
3. **Four residual design questions** in `docs/engineering/open-questions.md`, each blocking a later phase, none blocking Phase 1 (DW-02).

---

## Development Roadmap

Unchanged from the assessment, with Phase 0 now complete. Full version with rationale: [`docs/implementation/roadmap.md`](../docs/implementation/roadmap.md).

| # | Phase | Status |
|---|---|---|
| 0 | Documentation Reconciliation & Technical Baseline | ✅ **Complete** |
| 1 | Repository / Development Foundation | ✅ **Complete** |
| 2 | **Backend Foundation** | ⏳ **Next** |
| 3 | Shared Infrastructure (backend cross-cutting) | Not started |
| 4 | Angular 22 Web Foundation | Not started |
| 5 | Flutter Application Foundations | Not started |
| 6 | Authentication & Authorization | Not started |
| 7 | Administration & Tenant/Master Data | Not started |
| 8 | Customer Management | Not started |
| 9 | Inventory Management | Not started |
| 10 | Order Management | Not started |
| 11 | Delivery Management | Not started |
| 12 | Cylinder Ledger | Not started |
| 13 | Accounting & Billing | Not started |
| 14 | Notifications | Not started |
| 15 | Complaint Management | Not started |
| 16 | Reporting & Analytics | Not started |
| 17 | Printing | Not started |
| 18 | Production Hardening | Not started |
| 19 | CI/CD and Deployment | Incremental from phase 1 |
| 20 | Phase 2 / AI capabilities | Deferred per A-21 |

Two sequencing notes carried forward: **real-time and printing cross-cut** rather than being built once at the end, and **Administration precedes Customer Management** because master data is a hard prerequisite.

---

## Current Priority

### Phase 2 — Backend Foundation

**Not started. Awaiting explicit go-ahead.**

Phase 1 built the backend *skeleton*: app factory, settings, logging, errors, health, connections. Phase 2 builds the *machinery* that business features will sit on:

1. **Unit of Work** — the transaction boundary, with audit-row writing and post-commit event dispatch (`03-backend-architecture.md` §4).
2. **Base repository** and the aggregate↔ORM mapping conventions.
3. **Domain-event dispatcher**, in-process, with the transactional-outbox seam documented.
4. **Tenant-scoped session dependency** — the version that *requires* a resolved tenant context, closing DW-12. Note this genuinely depends on Authentication for the JWT, so part of it may have to land in Phase 6; worth resolving early in Phase 2 planning.
5. **First Alembic migration** — the `tenant` schema, with its RLS policies created in the same migration. **Against Supabase** (ADR-027): Alembic is the sole owner of schema, and the application role must be `NOSUPERUSER`/`NOBYPASSRLS`, never `service_role`.
6. **Tenant-isolation test suite** — two seeded tenants, every cross-tenant read returning nothing.
7. **Background worker** skeleton and the ARQ/Dramatiq/Celery decision (ADR-023, DW-06).
8. **Real-time publisher** implementation behind the existing port (ADR-015).
9. **Idempotency store**, caching, and rate limiting.

Still no business features. No Customer, Order, Inventory, Delivery, Accounting.

**First, though:** close out the five environment-blocked verifications by running `./scripts/dev-up.sh && ./scripts/check.sh` on a machine with a working Docker daemon.

---

## Next Step

Await explicit instruction to begin Phase 2.

When authorized: create `planning/features/02-backend-foundation/` with `PLAN.md`, `TASKS.md` and `STATUS.md` per `AGENTS.md` Step 3, then execute.

---

## Blockers

**None blocking Phase 2.**

One environment limitation carried forward:

- **Docker daemon unavailable in the Phase 1 environment.** Five verifications are marked blocked rather than complete (T-08, T-15, T-16, T-19, T-34). This blocks *closing out Phase 1's verification*, not starting Phase 2 — and it is an environment issue, not a code defect. Configuration is authored and validates.

---

## Open Questions

**None blocking Phase 1.**

All seven questions from the initial assessment were answered by the product owner on 2026-08-09. Deferred decisions each have a trigger point and none fall in Phase 1:

| Deferred decision | Needed by |
|---|---|
| Background job library (ARQ / Dramatiq / Celery) | Phase 2 |
| AG Grid Enterprise licence procurement | Phase 4 |
| Warehouse Staff vs Warehouse Manager (D-38 residual) | Phase 6 |
| KYC document types (pending business/legal) | Phase 8 |
| Inventory counter granularity (D-04/D-14 residual) | Phase 9 |
| Cancellation fee amount/configurability (D-19 residual) | Phase 10 |
| PDF rendering library (WeasyPrint / ReportLab) | Phase 17 |
| Statutory backup retention duration | Phase 18 |
| Azure hosting topology + IaC tool (Bicep / Terraform) | Before production |

One item is worth flagging early rather than at its trigger point: **AG Grid Enterprise is a paid product and procurement is unconfirmed.** It does not block Phase 1, but it does block Phase 4, and lead time on commercial licensing is outside engineering's control.

---

## Important Decisions

### Recorded in Phase 0 (ADR-012 … ADR-026)

| ADR | Decision |
|---|---|
| 012 | Python 3.13 + FastAPI backend; .NET architecture superseded, preserved |
| 013 | PostgreSQL as primary relational store (supersedes ADR-005) |
| 014 | Application services with an explicit cross-cutting pipeline (supersedes ADR-004/MediatR) |
| 015 | FastAPI WebSockets + Redis Pub/Sub; real-time is Phase 1 scope (supersedes ADR-007) |
| 016 | Python rendering stack for printing (amends ADR-010); library deferred |
| 017 | PostgreSQL RLS + repository scoping for tenant isolation (amends ADR-003) |
| 018 | Angular 22 + Nx workspace under `frontend/` |
| 019 | Signals-first state management with NgRx SignalStore |
| 020 | AG Grid Enterprise behind an application-level abstraction |
| 021 | RFC 7807 Problem Details as the API error contract |
| 022 | Azure target cloud; hosting topology and IaC tool deferred |
| 023 | Background job architecture; library deferred |
| 024 | `import-linter` + `mypy --strict` boundary enforcement |
| 025 | Polyglot monorepo layout; `frontend/` not renamed (amends ADR-001) |
| 026 | Code-first OpenAPI, generated spec committed as the frozen client contract |
| 027 | **Supabase as the managed PostgreSQL host only** — amends 013 and 022. Auth, Storage, Realtime and Edge Functions not adopted; Alembic keeps sole ownership of schema |

### Decisions that survived the stack change

Worth stating, because the change was narrower than the volume of edited text suggests: ADR-001 (monorepo), ADR-002 (modular monolith), ADR-003 (shared-DB multi-tenancy), ADR-006 (Flutter), ADR-008 (offline-first Driver App only), ADR-009 (URL versioning), ADR-010 (server-rendered printing), and ADR-011 (shared-library accessibility) all stand. What changed was the backend language and framework, the ORM, the relational engine, the in-process mediation mechanism, the real-time transport, and the rendering libraries.

### Binding business decisions (unchanged, discovered in assessment)

Multi-tenant SaaS from Phase 1 (D-01) · multi-branch/warehouse (D-02) · four customer types (D-03) · configurable cylinder types × 7 statuses (D-04, D-14) · offline-first Driver App is a Must-have (D-24) · WCAG 2.2 AA is Phase 1 (D-35) · binding performance SLAs (D-34) · jurisdiction India with GST (D-06) · Phase 1 excludes the AI/integration roadmap but must stay forward-compatible in the data model (A-21, D-36).

---

## Status

**COMPLETE** — for Phase 1, with 5 environment-blocked verifications recorded honestly as blocked rather than complete.

Phase 2 is **NOT STARTED**.

---

## Last Updated

2026-08-09
