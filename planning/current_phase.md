# Current Development Phase

## Project

LPG Agency Management Platform

---

## Current Phase

**Phase 0 — Documentation Reconciliation & Technical Baseline** ✅ **COMPLETE**

**Next phase — Phase 1: Repository / Foundation — NOT STARTED.** It requires an explicit go-ahead.

---

## Phase Objective

Make the documentation set unambiguous, so the first line of application code is written against a single coherent architecture — and so the reasoning behind the change stays traceable.

The repository contained two mutually exclusive architecture descriptions: `docs/architecture/` specified ASP.NET Core 8 / C# / EF Core / MediatR / Azure SQL; `AGENTS.md`, `knowledge/`, and all 20 documents in `docs/data/` specified Python 3.13 / FastAPI / SQLAlchemy / PostgreSQL. Both looked authoritative. `docs/architecture/03-backend-architecture.md` — the document an implementer would follow to lay out the backend — described MediatR pipeline behaviors carrying binding business rules (BR-28 audit logging, BR-30 tenant scoping) with no FastAPI equivalent written down anywhere.

**Objective achieved.** The backend stack is confirmed as Python/FastAPI/PostgreSQL, the .NET architecture is superseded through traceable ADRs with the original documents preserved, the missing Python architecture is authored, and the six cross-cutting contradictions are resolved.

---

## Current Repository State

Verified 2026-08-09, post-Phase-0.

**There is still no application source code. That is by design — Phase 0 was documentation-only.**

### Completed

| Area | State |
|---|---|
| Business analysis, SRS, business decisions D-01…D-42 | Complete, unchanged by Phase 0 |
| Data architecture (`docs/data/`, 20 docs incl. full PostgreSQL schema) | Complete, unchanged — it was already Python-native |
| UX architecture & design system (`docs/ui/`, 26 docs) | Complete, unchanged |
| **Solution architecture, reconciled to Python/FastAPI** | **Complete — 6 documents rewritten, 6 corrected in place, 1 created** |
| **Architecture Decision Records ADR-001 … ADR-026** | **Complete — 3 superseded, 3 amended, 15 added** |
| **Superseded .NET architecture, preserved** | **Complete — `docs/architecture/superseded/` with banners + README** |
| **Real-time architecture** | **Complete — new `16-realtime-architecture.md`** |
| **Implementation roadmap & module plan** | **Complete — resolved two dangling links** |
| **Documentation index & legacy path map** | **Complete — new `docs/README.md`** |
| Knowledge summaries | Updated to match the confirmed stack |
| `AGENTS.md`, `README.md` | Updated |
| Planning system | `planning/current_phase.md` + `planning/features/00-documentation-reconciliation/` |

### Not started

- Backend application (`backend/` is empty) — no FastAPI app, no layers, no models, no migrations, no tests
- Angular 22 dashboard (`frontend/` is empty) — no Nx workspace, no design tokens, no shared UI
- Flutter apps (`mobile/` is empty)
- Local development environment (Docker Compose, `.env` templates, seed scripts)
- CI/CD (`.github/` does not exist)
- Infrastructure as code (`infrastructure/` does not exist)
- `.gitignore`, `CONTRIBUTING.md`
- **Git: still zero commits.** Every file is untracked.

### Known documentation gap (recorded, not blocking)

Several documents reference per-module specification files under `docs/modules/` — `order-management.md`, `inventory-management.md`, `reporting.md`, `accounting.md`, `notifications.md`, `customer-management.md`. **That folder was never created.** Equivalent content is distributed across `docs/srs/functional.md`, `docs/business/`, `docs/engineering/`, and `docs/data/`; the mapping is documented in `docs/README.md` §Legacy Path Map, and per-module implementation scope is now consolidated in `docs/implementation/module-implementation-plan.md`.

Remaining `modules/` references inside `docs/business/` were deliberately left in place — those files are a stakeholder-approved historical record, and editing them to fix a path would alter the record for no functional gain.

---

## Technology Baseline

Confirmed by the product owner on 2026-08-09. Recorded as ADR-012 … ADR-026.

| Layer | Technology |
|---|---|
| Backend | Python 3.13+, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2 |
| Database | PostgreSQL, with Row-Level Security tenant isolation |
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

**Still nothing in code.** The baseline below is documented and internally consistent; it has not been built.

### Documented and unambiguous

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

### Gaps closed by Phase 0

All nine architecture gaps (A1–A9) from the initial assessment are closed: folder structure reconciled, docs sub-structure mapped, Python backend layering authored, the MediatR-equivalent designed, tenant isolation unified on PostgreSQL RLS, printing rebound to Python, real-time designed, background jobs designed, and boundary enforcement specified.

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
| 1 | **Repository / Foundation** | ⏳ **Next** |
| 2 | Backend Foundation | Not started |
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

### Phase 1 — Repository / Foundation

**Not started. Awaiting explicit go-ahead.**

Scope, when authorized:

1. `.gitignore` covering Python, Node/Nx, Flutter, and IDE artifacts — **before** anything else, so secrets and build output are never committed.
2. First commit of the existing documentation and planning tree.
3. Monorepo skeleton per `docs/architecture/14-folder-structure.md`: `backend/`, `frontend/`, `mobile/`, plus `infrastructure/`, `scripts/`, `.github/`.
4. Docker Compose for local PostgreSQL and Redis.
5. `.env.example` templates; no real secrets anywhere.
6. Root and per-stack lint/format configuration.
7. `CONTRIBUTING.md`.
8. A minimal CI workflow that runs on every PR.

**No business features. No FastAPI application code. No Angular application code. No Flutter applications.** Those are Phase 2, 4, and 5.

---

## Next Step

Await explicit instruction to begin Phase 1.

When authorized: create `planning/features/01-repository-foundation/` with `PLAN.md`, `TASKS.md`, and `STATUS.md` per `AGENTS.md` Step 3, then execute.

---

## Blockers

**None.**

Both blockers from the initial assessment are cleared:

- ~~B1: two mutually exclusive backend stacks documented as authoritative~~ — resolved by ADR-012 and the Phase 0 rewrites.
- ~~B2: no `.gitignore`, no commits~~ — still true, but it is now *scope of Phase 1* rather than a blocker to it.

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

### Decisions that survived the stack change

Worth stating, because the change was narrower than the volume of edited text suggests: ADR-001 (monorepo), ADR-002 (modular monolith), ADR-003 (shared-DB multi-tenancy), ADR-006 (Flutter), ADR-008 (offline-first Driver App only), ADR-009 (URL versioning), ADR-010 (server-rendered printing), and ADR-011 (shared-library accessibility) all stand. What changed was the backend language and framework, the ORM, the relational engine, the in-process mediation mechanism, the real-time transport, and the rendering libraries.

### Binding business decisions (unchanged, discovered in assessment)

Multi-tenant SaaS from Phase 1 (D-01) · multi-branch/warehouse (D-02) · four customer types (D-03) · configurable cylinder types × 7 statuses (D-04, D-14) · offline-first Driver App is a Must-have (D-24) · WCAG 2.2 AA is Phase 1 (D-35) · binding performance SLAs (D-34) · jurisdiction India with GST (D-06) · Phase 1 excludes the AI/integration roadmap but must stay forward-compatible in the data model (A-21, D-36).

---

## Status

**COMPLETE** — for Phase 0.

Phase 1 is **NOT STARTED**.

---

## Last Updated

2026-08-09
