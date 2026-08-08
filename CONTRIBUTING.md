# Contributing

## Before anything else

Read [`AGENTS.md`](./AGENTS.md). It is **authoritative** on workflow, architecture and standards, and it applies to human contributors and AI agents equally.

Then read [`planning/current_phase.md`](./planning/current_phase.md). Documentation describes intent; that file describes what actually exists right now.

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.13+ | backend |
| [uv](https://docs.astral.sh/uv/) | 0.8+ | Python dependency management |
| Node.js | 22+ | frontend |
| npm | 10+ | ships with Node |
| Flutter | 3.24+ (stable) | mobile |
| Docker Desktop | any current | PostgreSQL + Redis |
| Git | 2.40+ | |

## First-time setup

```bash
./scripts/setup.sh
```

That checks prerequisites, creates `.env` from `.env.example`, installs dependencies for all three stacks, and generates design tokens. Then:

```bash
./scripts/dev-up.sh
```

## Running things

| What | Command |
|---|---|
| PostgreSQL + Redis | `./scripts/dev-up.sh` / `./scripts/dev-down.sh` |
| Backend | `cd backend && uv run uvicorn lpg.api.app:app --reload` |
| Frontend | `cd frontend && npx nx serve dashboard` |
| Customer App | `cd mobile/apps/customer_app && flutter run` |
| Driver App | `cd mobile/apps/driver_app && flutter run` |

Backend on `http://localhost:8000`, API docs at `/api/v1/docs`, frontend on `http://localhost:4200`.

## Quality gates

```bash
./scripts/check.sh     # everything CI runs — run this before pushing
./scripts/test.sh      # tests only
./scripts/lint.sh      # lint + type check + boundaries (read-only)
./scripts/format.sh    # apply formatting
```

`check.sh` invokes the same commands CI does, rather than a parallel implementation. A local check that diverges from CI is worse than none — it produces false confidence.

---

## Non-negotiables

These are enforced by tooling, not by review. They will fail your build.

### Architecture boundaries

**Backend** — `import-linter` (ADR-024):

- `domain/` imports nothing from `application/`, `infrastructure/` or `api/`. Plain Python only: no FastAPI, no SQLAlchemy.
- `application/` imports `domain/` only, and defines ports (`Protocol`) that infrastructure implements.
- No SQLAlchemy outside `infrastructure/`. No FastAPI outside `api/`.
- The one exception is `api/app.py`, the composition root — that is what a composition root is for, and the exception is declared explicitly in `pyproject.toml`.

**Frontend** — Nx `enforce-module-boundaries` (ADR-018):

- Feature libraries never import each other. Cross-feature communication goes through `shared/data-access` or router navigation.

Both halves enforce module isolation the same way for the same reason: a dependency rule nobody checks is a dependency rule that erodes.

### Design tokens

Never hardcode a colour, spacing value, font size, radius, shadow or component dimension. Anywhere. In any stack.

Tokens come from **one source**: [`design-tokens/tokens.json`](./design-tokens/tokens.json). CSS variables, TypeScript constants and Dart constants are all generated from it:

```bash
node scripts/generate-tokens.mjs
```

Never hand-edit a generated token file. CI fails if generated output drifts from the source — because two hand-maintained token sets diverge within weeks, and the symptom is a Flutter screen that is subtly the wrong blue.

### The API contract

The OpenAPI spec is generated from Pydantic models and route metadata, committed to `backend/openapi/openapi.json`, and **that artifact is what clients generate from** (ADR-026).

Change an endpoint, regenerate:

```bash
cd backend && uv run python scripts/export_openapi.py
```

CI fails if the committed spec does not match. That converts "keep the spec up to date" from a discipline into a build failure, and makes every contract change visible in the diff.

### Error responses

RFC 7807 Problem Details, `application/problem+json`, extended with `error_code` (ADR-021). No `{"success": true, "data": ...}` envelope — HTTP status already carries that, and unwrapping a redundant envelope in three clients is pure ceremony.

Codes are catalogued in [`docs/data/18-error-catalog.md`](./docs/data/18-error-catalog.md).

### Tenant isolation

Every tenant-scoped table gets a Row-Level Security policy, created **in the same migration as the table**. Never out of band — otherwise an environment ends up with a table whose backstop is missing.

The application database role must never hold `BYPASSRLS`. Migrations run as the superuser role; the application does not.

### Accessibility

WCAG 2.2 AA is a **Phase 1 requirement** (D-35), not a later pass. Accessibility defects are functional defects.

---

## Feature workflow

Development is **one feature at a time**. Never build multiple business features in parallel.

Before writing any code, create:

```
planning/features/<NN>-<feature-name>/
    PLAN.md      scope, approach, files, risks, definition of done
    TASKS.md     small, independently verifiable tasks
    STATUS.md    live status
```

Then:

1. Mark the task in progress in `STATUS.md`.
2. Implement **only that task**.
3. Verify it — run the command, don't assume.
4. Mark it complete.
5. Move on.

**Never mark a task complete based on generated files alone.** If a build or test has not been run and passed, the task is not complete. If something cannot be verified in your environment, mark it **blocked** with the reason — never complete.

Work you discover along the way goes into `TASKS.md` as discovered work. Do not silently expand the task you are on.

Backend before frontend, always. A frontend built against an imagined API is rework waiting to happen.

## Commits

One logical change per commit.

```
feat(customer): add customer registration
fix(delivery): resolve inventory synchronisation
refactor(accounting): simplify payment validation
docs(architecture): supersede .NET deployment topology
```

Avoid `update`, `changes`, `fix`, `work`, `misc`.

## Pull requests

- Clear description and the requirement it satisfies
- Screenshots for UI changes
- API examples for backend changes
- Tests
- Documentation updates
- `./scripts/check.sh` passing locally

## Architecture decisions

Changing an architectural decision means writing an ADR in [`docs/architecture/15-architecture-decision-records.md`](./docs/architecture/15-architecture-decision-records.md).

**Never delete a superseded decision.** Mark it `Superseded`, link the replacement, explain why it changed, and keep the original text verbatim. `docs/architecture/superseded/` exists for exactly this reason and is historical only — never implement from it.
