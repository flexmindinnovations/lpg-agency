# LPG Agency Management Platform

An enterprise, multi-tenant SaaS platform that digitizes the complete LPG cylinder lifecycle for distributors — customers, bookings, inventory, delivery, the cylinder ledger, accounting, complaints, notifications, and reporting.

---

## Current state

**Phase 1 — Repository / Development Foundation.** The scaffolding, tooling and quality gates for all three stacks are in place and verified.

**No business features exist yet.** No authentication, no customers, no orders, no inventory. That is by design: each arrives in its own phase behind its own plan.

Authoritative status: [`planning/current_phase.md`](./planning/current_phase.md).

---

## Platform

| Application | Stack | Location |
|---|---|---|
| **Backend API** | Python 3.13 · FastAPI · SQLAlchemy 2.x · Alembic · Pydantic v2 · PostgreSQL · Redis | `backend/` |
| **Agency Web Dashboard** | Angular 22 · Nx · Signals · PrimeNG · Angular CDK (Material selective) · Tailwind CSS v4 · AG Grid Community (Enterprise optional) | `frontend/` |
| **Customer Mobile App** | Flutter · Riverpod · go_router | `mobile/apps/customer_app/` |
| **Driver Mobile App** | Flutter · Riverpod · go_router · Drift (offline-first) | `mobile/apps/driver_app/` |

**Architecture:** Clean Architecture · Domain-Driven Design · Modular Monolith · Multi-Tenant SaaS with PostgreSQL Row-Level Security · REST + WebSockets · design-token-driven UI · WCAG 2.2 AA

---

## Quick start

```bash
./scripts/setup.sh
```

Checks prerequisites, creates `.env`, installs dependencies for all three stacks, and generates design tokens. Then start the database:

```bash
./scripts/dev-up.sh
```

### Prerequisites

Python 3.13+ · [uv](https://docs.astral.sh/uv/) · Node.js 22+ · Flutter 3.24+ (stable) · Docker Desktop · Git

### Running

| What | Command | URL |
|---|---|---|
| PostgreSQL + Redis | `./scripts/dev-up.sh` | `localhost:55432` / `localhost:56379` |
| Backend | `cd backend && uv run uvicorn lpg.api.app:app --reload` | `http://localhost:8000` |
| API docs | — | `http://localhost:8000/api/v1/docs` |
| Frontend | `cd frontend && npx nx serve dashboard` | `http://localhost:4200` |
| Customer App | `cd mobile/apps/customer_app && flutter run` | device/emulator |
| Driver App | `cd mobile/apps/driver_app && flutter run` | device/emulator |

### Checks

| What | Command |
|---|---|
| Everything CI runs | `./scripts/check.sh` |
| Tests | `./scripts/test.sh` |
| Lint, types, boundaries | `./scripts/lint.sh` |
| Apply formatting | `./scripts/format.sh` |
| Regenerate design tokens | `node scripts/generate-tokens.mjs` |
| Regenerate OpenAPI spec | `cd backend && uv run python scripts/export_openapi.py` |

Run `./scripts/check.sh` before pushing — it invokes the same commands CI does.

---

## Repository layout

```
backend/         FastAPI application — domain / application / infrastructure / api
frontend/        Nx workspace containing the Angular 22 dashboard
mobile/          Flutter workspace — customer_app, driver_app, shared packages
design-tokens/   tokens.json — the single source for every platform's tokens
infrastructure/  Docker Compose for local PostgreSQL and Redis
scripts/         setup, dev, test, lint, format, check, token generation
docs/            Detailed specifications  →  docs/README.md
knowledge/       Concise summaries for developers and AI agents
planning/        Current phase + per-feature PLAN / TASKS / STATUS
.github/         CI workflows
```

---

## What is enforced

These fail the build. They are not style preferences.

| Rule | Mechanism |
|---|---|
| Clean Architecture dependency direction | `import-linter` contracts (backend) |
| Feature libraries never import each other | Nx `enforce-module-boundaries` (frontend) |
| Full type coverage at layer boundaries | `mypy --strict` |
| No hardcoded colours, spacing or type | Generated design tokens, drift-checked in CI |
| OpenAPI spec matches implementation | Committed artifact, drift-checked in CI |
| No environment file committed | Repository CI check |
| Superseded .NET architecture stays superseded | Repository CI check |

The reasoning behind each is in [`docs/architecture/15-architecture-decision-records.md`](./docs/architecture/15-architecture-decision-records.md) (ADR-001 … ADR-026).

---

## Where to start

| You want to… | Read |
|---|---|
| Contribute (human or AI) | [`AGENTS.md`](./AGENTS.md) — **authoritative**, then [`CONTRIBUTING.md`](./CONTRIBUTING.md) |
| Know what is happening now | [`planning/current_phase.md`](./planning/current_phase.md) |
| Understand the business | [`knowledge/00-project-overview.md`](./knowledge/00-project-overview.md) |
| Understand the architecture | [`knowledge/03-architecture-summary.md`](./knowledge/03-architecture-summary.md) |
| Know why a decision was made | [`docs/architecture/15-architecture-decision-records.md`](./docs/architecture/15-architecture-decision-records.md) |
| Know what the business decided | [`docs/business/decisions.md`](./docs/business/decisions.md) (D-01 … D-42) |
| See the delivery plan | [`docs/implementation/roadmap.md`](./docs/implementation/roadmap.md) |

---

## A note on `docs/architecture/superseded/`

That folder preserves an earlier ASP.NET Core / EF Core / Azure SQL architecture that was **superseded and never implemented**, retained so the decision history stays traceable.

**Do not implement from anything in it.** See [`docs/architecture/superseded/README.md`](./docs/architecture/superseded/README.md).
