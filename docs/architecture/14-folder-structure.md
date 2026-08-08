# 14 — Repository Folder Structure

## Purpose
Provides the authoritative repository layout across backend, Dashboard, mobile apps, documentation, planning, infrastructure, and CI/CD — so any engineer or AI agent can locate or place code correctly without guesswork.

## Scope
A structural reference, not implementation code. Rationale for each grouping is documented in the corresponding architecture document (cross-referenced inline).

> **Stack note.** Rewritten in Phase 0 (2026-08-09). The superseded version specified .NET solution/project names and a `/dashboard` folder that does not match this repository; it is preserved at [`superseded/14-folder-structure-dotnet.md`](./superseded/14-folder-structure-dotnet.md). See ADR-025.

## 1. Repository Strategy

**Single polyglot monorepo** housing the backend, Dashboard, and both mobile apps (ADR-001, ADR-025), chosen for:

- **Atomic cross-cutting changes** — an API contract change and its consuming Dashboard/mobile updates land in one pull request.
- **A single CI/CD pipeline definition** to maintain.
- **Enforceable shared conventions** — naming, design tokens, and the generated OpenAPI client across all three clients.

## 2. Top-Level Structure

```
lpg-agency/
  backend/          FastAPI application            → 03-backend-architecture.md §14
  frontend/         Nx workspace, Angular 22       → 04-frontend-architecture.md §8
  mobile/           Flutter workspace              → 05-mobile-architecture.md §8
  docs/             Detailed specifications        → §6
  knowledge/        Concise summaries for developers and AI agents
  planning/         Current phase + per-feature PLAN/TASKS/STATUS → §7
  infrastructure/   Infrastructure as code         → 13-deployment.md  (not yet created)
  scripts/          Local dev setup, seed data, code generation      (not yet created)
  .github/
    workflows/      CI/CD pipeline definitions     → 13-deployment.md §5  (not yet created)
  AGENTS.md         Authoritative AI development workflow
  README.md
  CONTRIBUTING.md                                                     (not yet created)
  .gitignore                                                          (not yet created)
```

**`frontend/` is the confirmed name and is not renamed to `dashboard/`.** The Nx *application* inside it may be named `dashboard`; the *folder* is `frontend/`. This is a deliberate, documented inconsistency — the documents were corrected to match the repository rather than the reverse (ADR-025).

Items marked *not yet created* are created in later phases, when they acquire content. They are documented here so their location is not improvised.

## 3. Backend (`backend/`)

Feature-based within each Clean Architecture layer, mirroring both the bounded contexts of `02-domain-driven-design.md` and the PostgreSQL schema names of `docs/data/03-database-schema.md`.

```
backend/
  src/lpg/
    domain/           # zero outward dependencies — plain Python
    application/      # depends on domain only; defines ports (Protocols)
    infrastructure/   # implements ports: SQLAlchemy, Redis, storage, jobs
    api/              # depends on application only: routers, schemas, middleware
    config/           # Pydantic BaseSettings
  migrations/         # Alembic
  tests/              # domain / application / infrastructure / api /
                      # tenant_isolation / architecture
  openapi/            # generated openapi.json, committed (ADR-026)
  pyproject.toml
```

The layer ordering is the dependency ordering. A module's position tells you what it may import. Full internal detail in `03-backend-architecture.md` §14; enforcement in §12.2 of the same document.

## 4. Frontend (`frontend/`)

```
frontend/
  apps/
    dashboard/
    dashboard-e2e/        # Playwright
  libs/
    features/             # customers, orders, delivery, inventory,
                          # accounting, complaints, reporting, tenant-admin
    shared/
      ui/                 # design-system components, incl. the AG Grid wrapper
      data-access/        # generated API client, shared state
      util/               # pipes, validators, formatters, keyboard shortcuts
      auth/
      design-tokens/
  tools/
  nx.json
  package.json
```

Full internal detail in `04-frontend-architecture.md` §8.

## 5. Mobile (`mobile/`)

```
mobile/
  apps/
    customer_app/
    driver_app/
  packages/
    core/
    design_system/
    api_client/           # generated from the committed OpenAPI spec
    auth/
    local_storage/        # Drift/SQLite
    sync_engine/          # offline-first sync, Driver App
  melos.yaml
```

Full internal detail in `05-mobile-architecture.md` §8.

## 6. Documentation (`docs/`)

This is the **actual** structure. Earlier documents referenced `/modules`, `/workflows`, `/requirements`, and `/questions`, which never existed; those references were corrected in Phase 0.

```
docs/
  business/         overview, stakeholders, glossary, business-rules,
                    assumptions, decisions (D-01…D-42), complaint-management
  srs/              functional, non-functional, security, performance, accessibility
  architecture/     01–16 (this folder)
    superseded/     preserved .NET-era architecture documents (ADR traceability)
  data/             01–20: domain model, ER diagram, PostgreSQL schema, indexing,
                    reference data, data dictionary, business rules, state machines,
                    domain events, API design, API contracts, OpenAPI conventions,
                    validation, sequence diagrams, reporting, printing, API security,
                    error catalog, data migration, integration contracts
  ui/               01–26: principles, personas, journeys, IA, screens, wireframes,
                    design system, tokens, color, typography, components, grids,
                    forms, shortcuts, a11y, printing UX, responsive, animation,
                    states, theming, Angular/Flutter guidelines, review checklist
  engineering/      workflow notes, open-questions status tracker
  implementation/   roadmap, module implementation plan, engineering standards,
                    testing strategy
  adr/              pointer to docs/architecture/15-architecture-decision-records.md
  LPG_Agency_Management_System_Blueprint.pdf   original source document
```

## 7. Planning (`planning/`)

```
planning/
  current_phase.md              single source of truth for what is being worked on now
  features/
    <NN>-<feature-name>/
      PLAN.md                   scope, approach, files, risks, definition of done
      TASKS.md                  task breakdown + discovered work
      STATUS.md                 live status
```

Per `AGENTS.md`, a feature must have all three files **before implementation begins**. Development is one feature at a time.

## 8. Infrastructure (`infrastructure/`) — not yet created

Created when the deferred hosting and IaC decisions are made (ADR-022, DW-05). Expected shape:

```
infrastructure/
  <iac-tool>/
    modules/          reusable modules: container host, postgres, redis,
                      blob storage, secret store, cdn
    environments/
      dev/ qa/ staging/ production/    per-environment parameters
  scripts/
```

The IaC tool (Bicep vs Terraform) is deliberately undecided — see `13-deployment.md` §1.

## 9. CI/CD (`.github/workflows/`) — not yet created

```
.github/workflows/
  backend-ci.yml      build, test, import-linter, mypy, OpenAPI drift check, security scan
  frontend-ci.yml     build, test, lint, a11y scan, e2e
  mobile-ci.yml       build, test (customer_app + driver_app)
  infra-ci.yml        IaC validation / plan
  deploy-dev.yml
  deploy-qa.yml
  deploy-staging.yml
  deploy-production.yml       manual-gated, per 13-deployment.md §5
```

Workflows are path-filtered so a change in one stack does not rebuild the others.

## 10. Testing Structure (Cross-Cutting Summary)

| Layer | Test types | Location |
|---|---|---|
| Backend Domain | Unit (aggregates, invariants, state machines) | `backend/tests/domain/` |
| Backend Application | Unit (use cases, fake repositories) | `backend/tests/application/` |
| Backend Infrastructure | Integration (repositories, mappers, migrations vs real PostgreSQL) | `backend/tests/infrastructure/` |
| Backend API | Integration/contract (full HTTP pipeline) | `backend/tests/api/` |
| Tenant Isolation | Cross-tenant access attempts (BR-30) | `backend/tests/tenant_isolation/` |
| Backend Architecture | `import-linter` contracts, model-registry assertions | `backend/tests/architecture/` |
| Dashboard | Unit (Jest), Component (Storybook + Testing Library), E2E (Playwright), a11y (axe-core) | `frontend/libs/**/*.spec.ts`, `frontend/apps/dashboard-e2e/` |
| Mobile | Widget, unit, integration/offline-sync | `mobile/apps/*/test/`, per-package `test/` |

Full strategy in `docs/implementation/testing-strategy.md`.

## 11. Best Practices

- **No cross-project imports that bypass architectural boundaries.** Frontend and mobile code never reach into backend internals — communication is exclusively via the generated API client, built from the committed OpenAPI spec (ADR-026).
- **Boundaries are enforced by tooling**, not convention: `import-linter` on the backend (ADR-024), Nx `enforce-module-boundaries` on the frontend (ADR-018).
- **Each top-level folder owns its own lint/format configuration**, consistent with a shared root config — avoiding both total fragmentation and a single rigid config that fits none of Python, TypeScript, and Dart well.
- **Generated artifacts are committed where they are contracts** (`backend/openapi/openapi.json`) and ignored where they are build output.

## 12. Risks

- **Monorepo build-time growth** — as all three clients and the backend grow, CI time can balloon. Mitigated by Nx affected-project detection on the frontend and path filtering in GitHub Actions for backend and mobile.
- **Structural drift** — folders created ad hoc during implementation diverging from this document. Mitigated by this document being the reference an agent consults before creating any new top-level path, per `AGENTS.md`.

## 13. Alternatives Considered

- **Polyrepo (separate repositories per client and backend)** — rejected per §1; revisit only if independent team ownership and release cadences make the monorepo's coordination overhead outweigh its benefits.
- **Renaming `frontend/` to `dashboard/`** for documentation consistency — rejected by explicit decision (ADR-025); the documents were corrected instead.

## 14. Future Improvements

- A dedicated versioned `contracts/` package (OpenAPI spec + generated clients) published as an artifact, if the platform ever needs to support genuinely external third-party API consumers beyond the three first-party clients.
