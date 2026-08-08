# PLAN — Phase 1: Repository / Development Foundation

**Feature ID:** 01-repository-foundation
**Phase:** Phase 1
**Type:** Foundation — infrastructure and tooling only, no business domain
**Created:** 2026-08-09
**Depends on:** [Phase 0 — Documentation Reconciliation](../00-documentation-reconciliation/STATUS.md) ✅ Complete

---

## Objective

Establish the production-ready repository structure and developer tooling required for the Angular 22, FastAPI, Flutter, PostgreSQL and Redis applications.

This phase establishes the foundation only. **No business-domain functionality is implemented.**

The test of success is narrow and concrete: a developer clones the repository, runs one setup command, and every application starts, every test suite runs, and every quality gate passes — with no business logic present.

---

## Scope

### Include

| Area | Deliverable |
|---|---|
| Repository structure | Top-level layout per `docs/architecture/14-folder-structure.md` |
| Git configuration | `.gitignore`, `.gitattributes`, first commit |
| Editor consistency | `.editorconfig` |
| Documentation | `README.md`, `CONTRIBUTING.md`, developer setup |
| Environment configuration | `.env.example` per stack; **no secrets committed** |
| Backend foundation | FastAPI app factory, settings, logging, correlation ID, RFC 7807 errors, health/readiness, CORS, OpenAPI, DB + Redis connections, Alembic baseline |
| Frontend foundation | Nx workspace, Angular 22 app shell, routing, layout, design tokens, theme system, shared libraries, API/data-access, error handling |
| Design system | Three-tier token architecture with Light / Dark / High-Contrast themes |
| Flutter foundation | Melos workspace, shared packages, two app shells, theme, routing, Drift local-storage foundation |
| Local dev environment | Docker Compose: PostgreSQL + Redis |
| Development scripts | Setup, run, test, lint, format, CI-equivalent |
| Code quality | Formatting, linting, type checking, boundary enforcement |
| Testing foundation | pytest, Jest, Playwright, flutter_test — smoke level only |
| CI foundation | GitHub Actions, validation only, no deployment |

### Exclude — explicitly out of scope

Authentication · RBAC · Customer Management · Inventory · Orders · Delivery · Cylinder Ledger · Accounting · Reporting · Notifications · Complaints · any business workflow · any domain aggregate · production infrastructure · deployment pipelines · offline synchronization logic.

The domain layer is created as an **empty package with base classes only** (`AggregateRoot`, `Entity`, `ValueObject`, `DomainEvent`). No business aggregate is defined.

---

## Architectural Basis

Every decision here is already made. This phase implements Phase 0's decisions; it does not revisit them.

| Decision | Source |
|---|---|
| Python 3.13 + FastAPI + SQLAlchemy 2.x + Alembic + Pydantic v2 | ADR-012 |
| PostgreSQL, RLS tenant isolation | ADR-013, ADR-017 |
| Application services, no mediator library | ADR-014 |
| FastAPI WebSockets + Redis Pub/Sub (not built this phase) | ADR-015 |
| Angular 22 + Nx workspace at `frontend/` | ADR-018 |
| Signals-first, NgRx SignalStore for justified shared state | ADR-019 |
| AG Grid Enterprise behind a wrapper | ADR-020 |
| RFC 7807 Problem Details error contract | ADR-021 |
| Background worker, library deferred (not built this phase) | ADR-023 |
| `import-linter` + `mypy --strict` boundary enforcement | ADR-024 |
| Polyglot monorepo, `frontend/` not renamed | ADR-025 |
| Code-first OpenAPI, generated spec committed | ADR-026 |
| Clean Architecture layer layout | `docs/architecture/03-backend-architecture.md` §14 |
| Three-tier design tokens, three themes | `docs/ui/09-design-tokens.md`, `10-color-system.md`, `11-typography.md` |

---

## Resolved Discrepancy — Flutter Folder Layout

The Phase 1 instruction sketches `mobile/customer/` and `mobile/driver/`. Phase 0's architecture documents (`docs/architecture/05-mobile-architecture.md` §8, `14-folder-structure.md` §5) specify:

```
mobile/apps/customer_app/ · mobile/apps/driver_app/ · mobile/packages/{core,design_system,api_client,auth,local_storage,sync_engine}
```

**Decision: follow the Phase 0 architecture.** Three reasons:

1. The same instruction says "Follow the architecture documentation created during Phase 0" and "go_router if selected by the reconciled architecture" — it defers to Phase 0 on mobile specifics.
2. Dart package names must be valid identifiers; `customer_app` is idiomatic, and the `apps/` + `packages/` split is what Melos expects.
3. The shared-packages layer is required by the documented offline-first Driver App architecture (D-24, ADR-008) — dropping it would foreclose Phase 5.

Both apps are still "customer" and "driver", which is what the sketch asked for. Flagged in the final report.

---

## Approach

### Sequencing

Dependency-ordered. Each group is independently verifiable.

```
A. Repository skeleton + Git         (nothing depends on a repo that ignores nothing)
      ↓
B. Local environment (Docker)         (backend integration tests need a real PostgreSQL)
      ↓
C. Backend foundation                 (frontend's generated client needs an OpenAPI spec)
      ↓
D. Frontend foundation
      ↓
E. Flutter foundation
      ↓
F. Scripts + CI + documentation       (describes what now exists)
      ↓
G. Verification
```

### Verification discipline

Per the instruction: *"Never mark a task complete based only on generated files."*

Every task has a **verification command** in `TASKS.md`. A task moves to Complete only after that command has been run and passed. Where a command cannot be run in this environment, the task is marked **Blocked** with the reason — never Complete.

### Secrets

`.env.example` files carry placeholder values only. `.gitignore` excludes `.env`, `*.env`, and `!*.env.example` before any environment file is written, so a real secret cannot be committed even accidentally.

---

## Key Design Decisions for This Phase

These are implementation-level choices within Phase 0's boundaries, recorded here rather than as ADRs because none of them change the architecture.

| Choice | Rationale |
|---|---|
| **uv** for Python dependency management | Named in the Phase 1 instruction; fast, lockfile-based, handles the Python version pin |
| **Ruff** for lint + format | Single tool replacing flake8/black/isort — fewer dependencies, which the instruction asks for |
| **PostgreSQL 17** and **Redis 7** in Compose | Current stable majors; `gen_random_uuid()` and RLS both long-established |
| **Design tokens as a JSON source + generator script** | `docs/ui/09-design-tokens.md` mandates a single platform-neutral source generating CSS/TS/Dart — a hand-maintained CSS file would violate it on day one |
| **Health split `/health/live` vs `/health/ready`** | `docs/architecture/12-observability.md` §5 — liveness restarts the container, readiness only removes it from rotation |
| **AG Grid wrapper stubbed, not implemented** | ADR-020 requires the abstraction to exist before any feature uses a grid. Licence is unprocured (DW-08), so the wrapper is created with the community package and a documented licence seam |
| **No `authGuard` / `permissionGuard`** | Those are Phase 6. Routing foundation only. |

---

## Files to Create — Summary

| Area | Approximate content |
|---|---|
| Root | `.gitignore`, `.gitattributes`, `.editorconfig`, `CONTRIBUTING.md`, updated `README.md` |
| `infrastructure/` | `docker/docker-compose.yml`, PostgreSQL init SQL, README |
| `scripts/` | setup, dev, test, lint, format, check (CI-equivalent), token generation |
| `backend/` | `pyproject.toml`, `src/lpg/{domain,application,infrastructure,api,config}`, `migrations/`, `tests/`, `.env.example` |
| `frontend/` | Nx workspace, `apps/dashboard`, `libs/shared/{design-tokens,ui,util,data-access}`, configs |
| `mobile/` | `melos.yaml`, `apps/{customer_app,driver_app}`, `packages/{core,design_system,local_storage}` |
| `.github/workflows/` | `backend-ci.yml`, `frontend-ci.yml`, `mobile-ci.yml`, `repo-ci.yml` |
| `design-tokens/` | `tokens.json` (single source), generator script |

---

## Testing Requirements

Smoke and foundation level only — business features do not exist.

| Stack | Tests |
|---|---|
| Backend | App factory constructs; `/health/live` returns 200; `/health/ready` reports dependency status; RFC 7807 shape on a forced error; correlation ID echoed; settings load from environment; DB and Redis connect (integration, requires Compose) |
| Frontend | App component renders; theme service switches all three themes; RFC 7807 interceptor maps an error; Playwright loads the shell |
| Flutter | Both apps build; theme resolves tokens; a widget smoke test per app |

---

## Definition of Done

Phase 1 is complete only when every item below is **verified by command**, not assumed:

- [ ] Repository structure established per `14-folder-structure.md`
- [ ] `.gitignore` exists and excludes secrets and build output
- [ ] Git configured; first commit made
- [ ] Backend starts successfully
- [ ] Backend health and readiness endpoints respond correctly
- [ ] Angular 22 application builds and starts
- [ ] Flutter applications build
- [ ] PostgreSQL dev environment works
- [ ] Redis dev environment works
- [ ] Environment configuration loads
- [ ] Tests execute and pass on all three stacks
- [ ] Linting passes
- [ ] Formatting passes
- [ ] Type checking passes
- [ ] Boundary contracts pass
- [ ] CI foundation defined and locally reproducible
- [ ] Documentation updated
- [ ] **No business feature implemented**
- [ ] `PLAN.md`, `TASKS.md`, `STATUS.md` current
- [ ] `planning/current_phase.md` reflects the new state

---

## Risks

| Risk | Mitigation |
|---|---|
| Docker daemon unavailable in this environment | Compose config is still authored and syntax-validated; integration verification marked Blocked with reason rather than claimed |
| AG Grid Enterprise licence unprocured (DW-08) | Wrapper built against the community package with a documented licence seam; no feature depends on Enterprise capabilities yet |
| Nx/Angular generator version drift | Pin versions; verify the actual installed Angular major after generation rather than assuming |
| Scope creep into Phase 2 | Domain package ships with base classes only; no aggregate, no repository, no use case |
| Token generator over-engineering | One small script, one JSON source, three outputs. No build-tool dependency added |

---

## Out-of-Scope Discoveries

Recorded in `TASKS.md` §Discovered Work, not implemented.
