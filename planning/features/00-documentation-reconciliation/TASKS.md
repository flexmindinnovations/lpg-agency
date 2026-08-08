# TASKS — Documentation Reconciliation & Technical Baseline

**Feature:** 00-documentation-reconciliation
**Plan:** [PLAN.md](./PLAN.md)
**Status:** [STATUS.md](./STATUS.md)

Legend: `[ ]` not started · `[~]` in progress · `[x]` complete · `[-]` intentionally not done (with reason)

---

## Group A — Decision Record (must be first; everything else cites these IDs)

- [x] **T-01** Mark ADR-004 (CQRS via in-process MediatR) **Superseded**, preserving original text, linking to its replacement.
- [x] **T-02** Mark ADR-005 (Azure SQL over Cosmos DB) **Superseded**, preserving original text, linking to its replacement.
- [x] **T-03** Mark ADR-007 (Azure SignalR Service) **Superseded**, preserving original text, linking to its replacement.
- [x] **T-04** Amend ADR-002 (modular monolith) and ADR-003 (shared-DB multi-tenancy) — decisions stand, enforcement mechanisms restated for the Python stack.
- [x] **T-05** Amend ADR-010 (server-rendered template printing) — decision stands, .NET renderer libraries superseded.
- [x] **T-06** Add ADR-012 … **ADR-026** recording every confirmed decision from PLAN.md §3. *(Scope grew from the planned 10 to 15 ADRs: boundary enforcement, monorepo layout, and the OpenAPI workflow each warranted their own record rather than being folded into others.)*
- [x] **T-07** Update the ADR summary table and the ADR document's Purpose/Format sections.

## Group B — Preserve the .NET Architecture (traceability constraint)

- [x] **T-08** Create `docs/architecture/superseded/` and its `README.md` explaining the set.
- [x] **T-09** Move the six stack-specific architecture documents into `superseded/` with `-dotnet` suffixes. **No deletions.**
- [x] **T-10** Prepend a SUPERSEDED banner to each moved document naming its replacement, superseding ADR, and reason.

## Group C — Python / FastAPI Backend Architecture

- [x] **T-11** Rewrite `docs/architecture/01-system-architecture.md` for the Python/FastAPI/PostgreSQL system. *(Reconciliation task 1)*
- [x] **T-12** Rewrite `docs/architecture/03-backend-architecture.md`: Clean Architecture layering for FastAPI. *(Tasks 3, 4)*
- [x] **T-13** Define the FastAPI equivalent of the five MediatR pipeline behaviors (validation, tenant scoping, audit logging, transaction, performance) in `03`. *(Task 5)*
- [x] **T-14** Define SQLAlchemy 2.x Unit of Work and repository boundaries in `03`. *(Task 6)*
- [x] **T-15** Define Python domain-event handling (in-process dispatcher, transactional outbox seam) in `03`. *(Task 8)*
- [x] **T-16** Define background-job architecture at a conceptual level in `03`. *(Task 9)*
- [x] **T-17** Define Python testing structure and architecture-boundary enforcement in `03`. *(Task 10)*
- [x] **T-18** Rewrite `docs/architecture/06-database-architecture.md`: PostgreSQL, RLS tenant isolation, migrations, indexing, backup. *(Task 7)*
- [x] **T-19** Create `docs/architecture/16-realtime-architecture.md`: FastAPI WebSockets + Redis Pub/Sub, transport abstraction, the five confirmed real-time use cases. *(Task 11)*
- [x] **T-20** Rewrite `docs/architecture/09-printing-architecture.md` for Python at a conceptual level. *(Task 12)*
- [x] **T-21** Rewrite `docs/architecture/13-deployment.md`: Azure direction, hosting topology and IaC tool explicitly deferred.
- [x] **T-22** Rewrite `docs/architecture/14-folder-structure.md` to match the actual polyglot monorepo. *(Task 18)*

## Group D — Targeted Architecture Corrections (in place)

- [x] **T-23** `02-domain-driven-design.md` — MediatR notifications → Python domain-event dispatcher.
- [x] **T-24** `07-api-architecture.md` — FluentValidation → Pydantic v2; ASP.NET policy authorization → FastAPI dependency authorization.
- [x] **T-25** `08-security-architecture.md` — ASP.NET Core Identity → FastAPI identity module; EF Core → SQLAlchemy; Azure SQL → PostgreSQL.
- [x] **T-26** `10-performance-strategy.md` — Azure SQL → PostgreSQL; `AsNoTracking()` → SQLAlchemy read patterns; SignalR → WebSocket/Redis.
- [x] **T-27** `12-observability.md` — Serilog → `structlog`; Hangfire → job runner; MediatR span → application-service span; ASP.NET health checks → FastAPI health endpoints.

## Group E — Frontend Reconciliation

- [x] **T-28** Rewrite `04-frontend-architecture.md` for Angular 22 + Nx under `frontend/`. *(Task 13)*
- [x] **T-29** Document the Signals-first + NgRx SignalStore rules with explicit "when to use which" guidance. *(Task 14)*
- [x] **T-30** Establish AG Grid Enterprise as standard, behind an application-level abstraction; document the commercial licence and the replaceability requirement. *(Task 15)*
- [x] **T-31** Remove PrimeNG as a default; resolve the optional TanStack Query question.

## Group F — Cross-Cutting Contradictions

- [x] **T-32** Resolve the RFC 7807 vs `{success, error}` contradiction in favour of RFC 7807 + `error_code`. *(Task 16)*
- [x] **T-33** Document the agreed OpenAPI workflow — code-first generation, generated spec frozen as the client contract. *(Task 17)*

## Group G — Documentation Hygiene

- [x] **T-34** Fix broken `docs/` directory cross-references across `knowledge/` and `docs/`. *(Task 19)*
- [x] **T-35** Fix the incorrect knowledge-file list in `knowledge/11-development-workflow.md`. *(Task 20)*
- [x] **T-36** Fix `AGENTS.md` references to current filenames and add the confirmed stack/paths. *(Task 21)*
- [x] **T-37** Reconcile `docs/adr/` — convert the misfiled duplicate to a pointer, add `README.md`. *(Task 22)*
- [x] **T-38** Repair `docs/implementation/README.md` links; create `roadmap.md` and `module-implementation-plan.md`. *(Task 23)*
- [x] **T-39** Reconcile `docs/implementation/engineering-standards.md` frontend section.
- [x] **T-40** Fix `docs/implementation/testing-strategy.md` architecture-test reference.
- [x] **T-41** Rewrite `README.md` — correct project name and add orientation.
- [x] **T-42** Clean stray `:contentReference[oaicite:N]{index=N}` export artifacts in `knowledge/09-engineering-standards.md`.

## Group H — Knowledge Summaries

- [x] **T-43** Update `knowledge/02-tech-stack.md` — Nx, NgRx SignalStore, WebSockets + Redis, AG Grid abstraction, corrected doc paths.
- [x] **T-44** Update `knowledge/03-architecture-summary.md` — real-time, folder layout, corrected mechanisms.
- [x] **T-45** Update `knowledge/05-api-standards.md` — RFC 7807, OpenAPI workflow, corrected doc paths.
- [x] **T-46** Update `knowledge/04`, `06`, `07`, `08` — corrected doc paths and stack-specific mechanisms.
- [x] **T-47** Update `knowledge/09-engineering-standards.md` — Nx, SignalStore, AG Grid, Python specifics.
- [x] **T-48** Rewrite `knowledge/12-current-status.md` to reflect the actual repository state. *(Task 24)*

## Group I — Verification & Closeout

- [x] **T-49** Run the contradiction check: no active-path document instructs an agent to build with .NET/EF Core/MediatR/Azure SQL/SignalR/FluentValidation/Serilog/Hangfire.
- [x] **T-50** Run the reference check: no document links to a non-existent `docs/` subdirectory.
- [x] **T-51** Verify all 14 exit-criteria questions are answerable.
- [x] **T-52** Update `planning/current_phase.md` and this feature's `STATUS.md`.
- [-] **T-53** Start Phase 1. **Not done — deliberately.** The user instructed: "Do NOT start Phase 1 automatically."

---

## Discovered Work (recorded, not implemented)

Per `AGENTS.md` §Scope Control, work discovered during this feature is recorded here rather than implemented.

| ID | Item | Why deferred |
|---|---|---|
| DW-01 | `docs/LPG_Agency_Management_System_Blueprint.pdf` has never been read by an agent; all markdown is derived from it | Derived docs are consistent and stakeholder-approved; re-deriving from source is a separate verification exercise |
| DW-02 | Four residual design questions in `docs/engineering/open-questions.md` (inventory counter granularity D-04/D-14, cancellation fee configurability D-19, offline-first timeline D-24, Warehouse Staff vs Warehouse Manager D-38) | Non-blocking for Phase 0/1; each becomes blocking at its own feature phase |
| DW-03 | KYC document types "to be supplied by business/legal" (A-20) | Blocks Customer Management (phase 8), not foundation |
| DW-04 | GST/statutory long-term backup retention duration unconfirmed | Blocks Production Hardening (phase 18) |
| DW-05 | Exact Azure hosting topology + IaC tool | Deliberately deferred by user decision; needs its own deployment ADR before production |
| DW-06 | Background-job library selection (ARQ / Celery / Dramatiq) | User asked for conceptual level only; decide at Phase 2 (Backend Foundation) with a spike |
| DW-07 | PDF rendering library selection (WeasyPrint / ReportLab) | Conceptual level only for Phase 0; decide at Phase 17 (Printing) with a rendering-fidelity spike |
| DW-08 | AG Grid Enterprise licence procurement is unconfirmed | Blocks Phase 4 (Angular Foundation) — flagged, not resolvable by an agent |
| DW-09 | `docs/modules/*.md` per-module specifications are referenced by several documents but **were never created**. Equivalent content is distributed across `docs/srs/functional.md`, `docs/business/`, `docs/engineering/`, `docs/data/`; mapped in `docs/README.md` §Legacy Path Map and consolidated at implementation level in `docs/implementation/module-implementation-plan.md` | Not blocking — every module's requirements are documented somewhere. Consolidation would be worthwhile before each module's own implementation phase |
| DW-10 | Legacy `modules/` path references remain inside `docs/business/*.md` | Deliberate. Those files are a stakeholder-approved historical record; editing them to fix a path would alter the record for no functional gain. Resolvable via `docs/README.md` §Legacy Path Map |
