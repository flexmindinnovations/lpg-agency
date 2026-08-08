> # ⛔ SUPERSEDED — DO NOT IMPLEMENT FROM THIS DOCUMENT
>
> | | |
> |---|---|
> | **Status** | Superseded on 2026-08-09 |
> | **Replaced by** | [`docs/architecture/14-folder-structure.md`](../14-folder-structure.md) |
> | **Superseding ADRs** | ADR-012 (FastAPI), ADR-018 (Angular 22 + Nx), ADR-025 (repository layout) — see [`15-architecture-decision-records.md`](../15-architecture-decision-records.md) |
> | **Original path** | `docs/architecture/14-folder-structure.md` |
>
> **Why superseded:** this document specifies **.NET solution/project layout** (`LpgPlatform.Domain`, `LpgPlatform.Application`, `LpgPlatform.Infrastructure`, `LpgPlatform.Api`, `LpgPlatform.Contracts`, `LpgPlatform.sln`, NetArchTest projects) and top-level folder names that do not match the repository. It calls the web folder `/dashboard` — the repository uses **`frontend/`**, which is confirmed to stay. Its `/docs` sub-structure (`/modules`, `/workflows`, `/requirements`, `/questions`) also never existed; the real one is `/business`, `/srs`, `/data`, `/ui`, `/architecture`, `/engineering`, `/implementation`, `/adr`.
>
> **What survives:** the single-monorepo decision (ADR-001 stands), the rationale for it, the boundary rule against cross-project imports, per-stack lint configuration, the CI build-time growth risk, and the polyrepo alternative analysis.
>
> **Retained for:** decision traceability. See `docs/architecture/superseded/README.md`.

---

# 14 — Repository Folder Structure

## Purpose
Provides the complete, authoritative repository layout across backend, Dashboard, Customer App, Driver App, shared libraries, documentation, testing, and CI/CD — so any engineer can locate or place code correctly without guesswork.

## Scope
This is a structural reference, not implementation code. Rationale for each major grouping is documented in the corresponding architecture document (cross-referenced inline).

## 1. Repository Strategy

**Single monorepo** housing backend, Dashboard, and both mobile apps, chosen for: atomic cross-cutting changes (e.g., an API contract change and its consuming Dashboard/mobile update land in one PR), a single CI/CD pipeline definition to maintain, and easier enforcement of shared conventions (naming, design tokens, OpenAPI-generated clients) across all three clients. Documented as ADR-001 in `15-architecture-decision-records.md`.

## 2. Top-Level Structure

```
/lpg-agency-platform
  /backend                     -> see 03-backend-architecture.md §7
  /dashboard                   -> Nx workspace, see 04-frontend-architecture.md §8
  /mobile                      -> Flutter workspace, see 05-mobile-architecture.md §8
  /docs
    /business
    /modules
    /workflows
    /requirements
    /questions
    /architecture
  /infrastructure              -> Bicep IaC, see 13-deployment.md §4
  /.github
    /workflows                 -> CI/CD pipeline definitions
  /scripts                     -> local dev setup, seed data, code-gen scripts
  README.md
  CONTRIBUTING.md
```

## 3. Backend (`/backend`)

```
/backend
  /src
    /LpgPlatform.Domain
    /LpgPlatform.Application
    /LpgPlatform.Infrastructure
    /LpgPlatform.Api
    /LpgPlatform.Contracts
  /tests
    /LpgPlatform.Domain.Tests
    /LpgPlatform.Application.Tests
    /LpgPlatform.Infrastructure.Tests
    /LpgPlatform.Api.IntegrationTests
    /LpgPlatform.ArchitectureTests
  /openapi                     -> generated OpenAPI spec, published artifact
  LpgPlatform.sln
```
(Full internal detail in `03-backend-architecture.md` §7.)

## 4. Dashboard (`/dashboard`)

```
/dashboard
  /apps
    /dashboard
    /dashboard-e2e             -> Playwright
  /libs
    /features
      /customers, /orders, /delivery, /inventory, /accounting, /complaints, /reporting, /tenant-admin
    /shared
      /ui, /data-access, /util, /auth, /design-tokens
  nx.json
  package.json
```
(Full internal detail in `04-frontend-architecture.md` §8.)

## 5. Mobile (`/mobile`)

```
/mobile
  /apps
    /customer_app
    /driver_app
  /packages
    /core, /design_system, /local_storage, /sync_engine, /auth, /api_client
  /test
  melos.yaml
```
(Full internal detail in `05-mobile-architecture.md` §8.)

## 6. Documentation (`/docs`)

```
/docs
  /business        -> overview, stakeholders, glossary, business-rules, assumptions, decisions
  /modules         -> one file per business module (incl. complaint-management)
  /workflows       -> customer-booking, delivery-flow, inventory-flow, payment-flow, cylinder-ledger
  /requirements    -> functional, non-functional, security, performance, accessibility
  /questions       -> open-questions (status tracker)
  /architecture    -> this folder (01 through 15)
```

## 7. Infrastructure (`/infrastructure`)

```
/infrastructure
  /bicep
    /modules            -> reusable Bicep modules (app-service, sql, redis, blob, keyvault, signalr)
    /environments
      /dev, /qa, /staging, /production   -> per-environment parameter files
  /scripts              -> deployment helper scripts
```

## 8. CI/CD (`/.github/workflows`)

```
/.github/workflows
  backend-ci.yml           -> build, test, arch-tests, lint, security scan
  dashboard-ci.yml         -> build, test, lint, a11y scan, e2e
  mobile-ci.yml            -> build, test (customer_app + driver_app)
  infra-ci.yml             -> Bicep validation/what-if
  deploy-dev.yml
  deploy-qa.yml
  deploy-staging.yml
  deploy-production.yml    -> manual-gated, per 13-deployment.md §3
```

## 9. Testing Structure (Cross-Cutting Summary)

| Layer | Test Types | Location |
|---|---|---|
| Backend Domain | Unit tests (aggregates, invariants) | `/backend/tests/LpgPlatform.Domain.Tests` |
| Backend Application | Unit tests (handlers, validators, behaviors) | `/backend/tests/LpgPlatform.Application.Tests` |
| Backend Infrastructure | Integration tests (repositories against test DB) | `/backend/tests/LpgPlatform.Infrastructure.Tests` |
| Backend API | Integration/contract tests (full HTTP pipeline) | `/backend/tests/LpgPlatform.Api.IntegrationTests` |
| Backend Architecture | NetArchTest boundary/dependency-direction rules, tenant-isolation assertions | `/backend/tests/LpgPlatform.ArchitectureTests` |
| Dashboard | Unit (Jest), Component (Storybook + Testing Library), E2E (Playwright), a11y (axe-core) | `/dashboard/libs/**/*.spec.ts`, `/dashboard/apps/dashboard-e2e` |
| Mobile | Widget tests, unit tests, integration/offline-sync tests | `/mobile/test`, per-package `/test` |

## 10. Best Practices
- No cross-project imports that bypass the boundaries defined in `01-system-architecture.md`/`04-frontend-architecture.md` (e.g., Dashboard code must never import backend `Domain`/`Infrastructure` projects directly — communication is via the generated API client only).
- Every top-level folder owns its own linting/formatting configuration consistent with a shared root config, avoiding both total fragmentation and an overly rigid single config that doesn't fit each stack's idioms (.NET vs. TypeScript vs. Dart).

## 11. Risks
- **Monorepo build-time growth**: as all three clients and the backend grow, CI build time can balloon — mitigated by Nx's affected-project detection (only rebuild/retest what changed) on the Dashboard side, and analogous path-filtering in GitHub Actions for backend/mobile workflows.

## 12. Alternatives Considered
- **Polyrepo (separate repos per client/backend)** — rejected per §2 rationale; revisit only if independent team ownership/release cadences make the monorepo's coordination overhead outweigh its benefits.

## 13. Future Improvements
- Introduce a dedicated `/contracts` versioned package (OpenAPI spec + generated clients) as a publishable artifact if the platform ever needs to support genuinely external/third-party API consumers beyond the three first-party clients.
