# PLAN — Documentation Reconciliation & Technical Baseline

**Feature ID:** 00-documentation-reconciliation
**Phase:** Phase 0 (foundation, pre-implementation)
**Type:** Documentation only — no application source code
**Owner:** AI development agent
**Created:** 2026-08-09

---

## 1. Business Goal

The repository contains two mutually exclusive, internally consistent architecture descriptions. `docs/architecture/` specifies an **ASP.NET Core 8 / C# / EF Core / MediatR / Azure SQL** system; `AGENTS.md`, `knowledge/`, and `docs/data/` specify a **Python 3.13 / FastAPI / SQLAlchemy 2.x / PostgreSQL** system.

Any developer or AI agent starting implementation today will read authoritative-looking guidance for the wrong stack. The business goal of this feature is to make the documentation set **unambiguous**, so that the first line of application code is written against a single, coherent, verified architecture — and so that the reasoning behind the change remains traceable to future maintainers.

This is not a cosmetic cleanup. `docs/architecture/03-backend-architecture.md` is the document an implementer would follow to lay out the backend; it currently describes MediatR pipeline behaviors that carry real business rules (BR-28 audit logging, BR-30 tenant scoping) and have no FastAPI equivalent written down anywhere.

## 2. Scope

### In scope

- Establishing Python/FastAPI/PostgreSQL as the authoritative backend architecture.
- Superseding the .NET-era architecture decisions through traceable ADRs, preserving the historical documents.
- Authoring the missing Python/FastAPI backend architecture documentation.
- Reconciling the Angular 22 + Nx frontend architecture.
- Resolving the six documented contradictions (error contract, OpenAPI workflow, state management, data grid, real-time transport, folder structure).
- Repairing broken cross-references across `docs/` and `knowledge/`.
- Updating `AGENTS.md`, `README.md`, `knowledge/12-current-status.md`, and `planning/current_phase.md`.

### Explicitly out of scope

- Any application source code (Python, TypeScript, Dart, SQL).
- Dependency installation or lockfiles.
- Angular / Nx / FastAPI / Flutter scaffolding.
- Docker, Docker Compose, CI workflows, IaC.
- `.gitignore` and the first commit (these belong to Phase 1 — Repository / Foundation).
- Re-litigating business decisions D-01 … D-42. They are stakeholder-confirmed and binding.
- The exact Azure hosting topology and IaC tool (explicitly deferred by the user to a later deployment architecture decision).

## 3. Confirmed Decisions Driving This Work

Confirmed by the user on 2026-08-09:

| Area | Decision |
|---|---|
| Backend | Python 3.13+, FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL, Redis, Pydantic v2 |
| .NET architecture | Superseded — corrected, **not deleted**; supersession recorded in ADRs |
| Frontend | Angular 22, strict TypeScript, **Nx**, Signals, Angular Material, Angular CDK, Tailwind CSS v4, AG Grid Enterprise, Storybook, Jest, Playwright |
| Frontend folder | Remains `frontend/` — **not** renamed to `dashboard/`; the Angular app lives inside an Nx workspace under `frontend/` |
| State management | Signals-first. NgRx SignalStore for justified complex/shared feature state. No classic NgRx Store/Actions/Reducers without a documented need. RxJS for HTTP, WebSockets, async streams, library interop. No state library for simple component state. |
| Data grid | AG Grid Enterprise, **encapsulated behind application-level reusable grid components**; features must not couple to AG Grid APIs; commercial licence documented; architecture kept replaceable |
| Repository layout | Polyglot monorepo: `backend/ frontend/ mobile/ docs/ knowledge/ planning/ infrastructure/ scripts/ .github/`. No existing top-level directory renamed. |
| Mobile | Flutter, Riverpod, Drift SQLite. Customer App and Driver App are separate apps sharing common packages. Driver App offline-first. |
| Real-time | **Phase 1 requirement.** FastAPI WebSockets + Redis Pub/Sub. Azure SignalR is not carried forward. Transport abstracted so it can evolve. Covers order status, delivery status, driver assignment, dispatcher operations, dashboard live updates. |
| Cloud | Azure remains the target. Exact hosting topology (Container Apps vs App Service vs other) and IaC tool (Bicep vs Terraform) deliberately **not** locked — to be decided in a deployment architecture decision before production. Phase 0 establishes Azure-compatible direction only. |

## 4. Approach

### 4.1 Preservation strategy (the traceability constraint)

The user's constraint is explicit: *"Do not silently rewrite large amounts of documentation without preserving traceability."*

Two mechanisms are used together:

1. **Document-level preservation.** Architecture documents whose substance is stack-specific and must be replaced wholesale are **moved**, not deleted, to `docs/architecture/superseded/`, renamed with a `-dotnet` suffix, and given a prominent SUPERSEDED banner naming the replacement document, the superseding ADR, and the reason. A `README.md` in that folder explains the whole set.
2. **Decision-level preservation.** `docs/architecture/15-architecture-decision-records.md` follows its own stated convention (§Review Cadence: *"superseded decisions are marked Superseded, with a link to the new ADR, never deleted"*). Affected ADRs keep their original Context/Decision/Consequences text verbatim, gain a `Superseded by ADR-0NN` status line and a "Why superseded" paragraph, and new ADRs record each replacement decision.

Documents containing only incidental .NET references (a library name, one diagram node) are edited in place; the ADR record carries the traceability.

### 4.2 Sequencing

Documentation has dependencies just as code does. The order is:

```
ADRs (decision record)
   ↓
Backend architecture (01, 03, 06, 09, 13, 14, 16)
   ↓
Frontend architecture (04)
   ↓
Implementation-level docs (docs/implementation/*)
   ↓
Knowledge summaries (knowledge/*)
   ↓
Entry points (AGENTS.md, README.md, planning/current_phase.md)
```

ADRs are written first so every subsequent document can cite a stable decision ID. Entry points are written last so they describe the finished state.

### 4.3 Consistency rules applied throughout

- Backend module/package names use `snake_case` matching the PostgreSQL schema names already fixed in `docs/data/03-database-schema.md` (`tenant`, `customer`, `orders`, `delivery`, `inventory`, `ledger`, `accounting`, `complaints`, `identity`, `audit`).
- JSON field naming stays `snake_case`, per the decision already recorded in `docs/data/10-api-design-guidelines.md` §Design Decision.
- The error contract is **RFC 7807 Problem Details extended with `error_code`**, matching `docs/data/10` §12 and `docs/data/18-error-catalog.md`.
- No document may state a technology choice that contradicts §3 of this plan.

## 5. Files to Create

| Path | Purpose |
|---|---|
| `docs/architecture/superseded/README.md` | Explains the superseded set, why it exists, and what replaced each document |
| `docs/architecture/16-realtime-architecture.md` | FastAPI WebSockets + Redis Pub/Sub real-time architecture (new capability doc) |
| `docs/adr/README.md` | Points `docs/adr/` at the real ADR document; corrects the misfiled duplicate |
| `docs/implementation/roadmap.md` | Phase 1 / Phase 2 delivery split (resolves a dangling link) |
| `docs/implementation/module-implementation-plan.md` | Per-bounded-context implementation sequence (resolves a dangling link) |
| `planning/features/00-documentation-reconciliation/PLAN.md` | This file |
| `planning/features/00-documentation-reconciliation/TASKS.md` | Task breakdown |
| `planning/features/00-documentation-reconciliation/STATUS.md` | Live status |

## 6. Files to Move (preserved, not deleted)

| From | To |
|---|---|
| `docs/architecture/01-system-architecture.md` | `docs/architecture/superseded/01-system-architecture-dotnet.md` |
| `docs/architecture/03-backend-architecture.md` | `docs/architecture/superseded/03-backend-architecture-dotnet.md` |
| `docs/architecture/06-database-architecture.md` | `docs/architecture/superseded/06-database-architecture-dotnet.md` |
| `docs/architecture/09-printing-architecture.md` | `docs/architecture/superseded/09-printing-architecture-dotnet.md` |
| `docs/architecture/13-deployment.md` | `docs/architecture/superseded/13-deployment-dotnet.md` |
| `docs/architecture/14-folder-structure.md` | `docs/architecture/superseded/14-folder-structure-dotnet.md` |

Each moved file gains a SUPERSEDED banner. Each canonical path is then rewritten for the Python/FastAPI stack.

## 7. Files to Modify

**Architecture (in place):**
- `docs/architecture/02-domain-driven-design.md` — MediatR notification reference → Python domain-event dispatcher
- `docs/architecture/04-frontend-architecture.md` — Angular 20→22, `frontend/` path, AG Grid Enterprise + abstraction, SignalR→WebSocket, PrimeNG removal, TanStack Query resolution
- `docs/architecture/07-api-architecture.md` — FluentValidation→Pydantic v2, ASP.NET policy authorization→FastAPI dependency authorization
- `docs/architecture/08-security-architecture.md` — ASP.NET Identity→FastAPI identity, EF Core→SQLAlchemy, Azure SQL→PostgreSQL
- `docs/architecture/10-performance-strategy.md` — Azure SQL→PostgreSQL, `AsNoTracking()`→SQLAlchemy read patterns, SignalR→WebSocket/Redis
- `docs/architecture/12-observability.md` — Serilog→`structlog`, Hangfire→job runner, MediatR→application-service span, ASP.NET health checks→FastAPI health endpoints
- `docs/architecture/15-architecture-decision-records.md` — supersessions + new ADRs

**Implementation:**
- `docs/implementation/README.md` — repair links
- `docs/implementation/engineering-standards.md` — frontend section (NgRx-or-Elf, `async` pipe, `@Input()`/`@Output()`, Cypress) reconciled to Signals-first + Playwright + Storybook
- `docs/implementation/testing-strategy.md` — NetArchTest → Python boundary enforcement

**Business/engineering:**
- `docs/business/assumptions.md` — `questions/open-questions.md` path reference
- `docs/engineering/open-questions.md` — `business/decisions.md` path reference
- `docs/adr/decisions.md` — converted to a pointer stub (content preserved at `docs/business/decisions.md`)

**Knowledge:**
- `knowledge/02-tech-stack.md`, `03-architecture-summary.md`, `04-data-summary.md`, `05-api-standards.md`, `06-security-summary.md`, `07-ui-ux-summary.md`, `08-printing-summary.md`, `09-engineering-standards.md`, `11-development-workflow.md`, `12-current-status.md`

**Entry points:**
- `AGENTS.md`, `README.md`, `planning/current_phase.md`

## 8. APIs / Database / UI Changes

None. This feature produces no runnable artifact.

The API **contract documentation** is clarified (RFC 7807, code-first OpenAPI generation), and the database **documentation** is corrected from Azure SQL to PostgreSQL, but `docs/data/03-database-schema.md` — the authoritative physical schema — is already PostgreSQL-native and is not modified.

## 9. Testing Requirements

No automated tests (no code). Verification is by inspection against the exit criteria:

| # | Question an agent must be able to answer unambiguously |
|---|---|
| 1 | What technology stack are we building? |
| 2 | Where does backend code live? |
| 3 | Where does Angular code live? |
| 4 | Where does Flutter code live? |
| 5 | What is the backend architecture? |
| 6 | What is the frontend architecture? |
| 7 | How is state managed? |
| 8 | How is tenant isolation enforced? |
| 9 | How are APIs defined? |
| 10 | How is real-time communication implemented? |
| 11 | How are background jobs handled? |
| 12 | How is printing implemented? |
| 13 | How are tests structured? |
| 14 | What is the next development phase? |

Plus two mechanical checks:

- **Contradiction check:** no document on an active (non-`superseded/`) path instructs an agent to build with .NET, EF Core, MediatR, Azure SQL, SignalR, FluentValidation, Serilog, or Hangfire.
- **Reference check:** no document links to a `docs/` subdirectory that does not exist.

## 10. Risks

| Risk | Mitigation |
|---|---|
| Rewriting architecture docs loses hard-won reasoning that was stack-independent (e.g. why a modular monolith, why relational over NoSQL) | Rewrites carry forward the original rationale wherever it survives the stack change; ADRs preserve original text verbatim |
| A superseded document is later read as current | Physical relocation to `superseded/` + banner on every file + folder README |
| Over-specifying the Python backend beyond what has been decided | Conceptual level only for background jobs and printing libraries, per user instruction; specific library selections flagged as open where genuinely undecided |
| Scope creep into Phase 1 scaffolding | Explicit out-of-scope list in §2; no file outside `docs/`, `knowledge/`, `planning/`, `AGENTS.md`, `README.md` is touched |

## 11. Definition of Done

- All 24 reconciliation tasks in `TASKS.md` are complete.
- All 14 exit-criteria questions answerable from `AGENTS.md` → `knowledge/` → `docs/` → `planning/current_phase.md`.
- Contradiction check and reference check both pass.
- `planning/current_phase.md`, `knowledge/12-current-status.md`, and this feature's `STATUS.md` updated.
- **Stop.** Phase 1 is not started automatically.
