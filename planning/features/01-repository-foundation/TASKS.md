# TASKS — Phase 1: Repository / Development Foundation

**Feature:** 01-repository-foundation
**Plan:** [PLAN.md](./PLAN.md) · **Status:** [STATUS.md](./STATUS.md)

Legend: `[ ]` not started · `[~]` in progress · `[x]` complete (verified) · `[!]` blocked · `[-]` intentionally not done

**A task is complete only when its Verify command has been run and passed.** Generated files alone are not completion.

---

## Group A — Repository Skeleton & Git

- [ ] **T-01** Create `.gitignore` covering Python, Node/Nx, Flutter/Dart, Docker, IDE, OS artifacts. Must exclude `.env` while allowing `.env.example`.
  *Verify:* `git status --porcelain` shows no `.env`, `node_modules`, `__pycache__`, or build output.
- [ ] **T-02** Create `.gitattributes` (line-ending normalization — the repo is on Windows, CI is Linux).
  *Verify:* file exists; `git check-attr text -- backend/pyproject.toml` reports `text: auto`.
- [ ] **T-03** Create `.editorconfig` matching each stack's conventions.
  *Verify:* file exists and parses; indent rules present for `.py`, `.ts`, `.dart`, `.yml`, `.md`.
- [ ] **T-04** Create top-level directory skeleton: `infrastructure/`, `scripts/`, `.github/workflows/`, `design-tokens/`.
  *Verify:* all directories exist and each contains at least one tracked file.

## Group B — Local Development Environment

- [ ] **T-05** Author `infrastructure/docker/docker-compose.yml` — PostgreSQL 17 + Redis 7, named volumes, healthchecks, non-default ports to avoid collisions.
  *Verify:* `docker compose config` parses without error.
- [ ] **T-06** PostgreSQL init script — extensions and the non-superuser application role required by RLS (ADR-017: the app role must not hold `BYPASSRLS`).
  *Verify:* SQL file present and referenced by Compose; syntax reviewed.
- [ ] **T-07** Create `.env.example` files (root, backend). Placeholders only — no real secrets.
  *Verify:* `grep -rE '(password|secret|key)\s*=\s*\S{16,}' *.env.example` returns nothing meaningful; `.env` is git-ignored.
- [ ] **T-08** Bring the environment up and confirm both services are healthy.
  *Verify:* `docker compose ps` shows both healthy; `docker compose exec postgres pg_isready`; `redis-cli ping` → PONG.

## Group C — Backend Foundation (FastAPI)

- [ ] **T-09** Initialize the uv project: `pyproject.toml`, Python 3.13 pin, dependency groups.
  *Verify:* `uv sync` succeeds; `uv run python -c "import sys; print(sys.version)"` reports 3.13.
- [ ] **T-10** Create the Clean Architecture package skeleton: `domain/`, `application/`, `infrastructure/`, `api/`, `config/` with base classes only.
  *Verify:* `uv run python -c "import lpg"` succeeds; no business aggregate exists.
- [ ] **T-11** Settings/configuration via Pydantic v2 `BaseSettings`, loaded from environment.
  *Verify:* unit test asserts settings load and that a missing required var fails loudly.
- [ ] **T-12** Structured logging foundation (`structlog`), JSON output, with a redaction processor.
  *Verify:* test asserts JSON output and that a secret-named field is redacted.
- [ ] **T-13** Correlation-ID middleware — accept inbound header or generate; bind to log context; echo on response.
  *Verify:* test asserts the response header is present and echoes a supplied ID.
- [ ] **T-14** RFC 7807 exception handling foundation (ADR-021) with `error_code` extension.
  *Verify:* test asserts `application/problem+json`, and presence of `type`/`title`/`status`/`error_code`.
- [ ] **T-15** Database connection foundation — async SQLAlchemy 2.x engine, session factory, tenant-context seam.
  *Verify:* integration test connects to Compose PostgreSQL and executes `SELECT 1`.
- [ ] **T-16** Redis connection foundation — async client, lifecycle-managed.
  *Verify:* integration test PINGs Compose Redis.
- [ ] **T-17** Health and readiness endpoints — `/health/live` (process) and `/health/ready` (dependencies).
  *Verify:* test asserts live returns 200 unconditionally; ready reports per-dependency status.
- [ ] **T-18** App factory: CORS, OpenAPI metadata, versioned `/api/v1` router, lifespan management.
  *Verify:* app starts; `/api/v1/openapi.json` is valid OpenAPI 3.1.
- [ ] **T-19** Alembic baseline — configured against the async engine, no migrations yet.
  *Verify:* `uv run alembic current` runs without error against Compose PostgreSQL.
- [ ] **T-20** pytest foundation — async support, fixtures, unit/integration split.
  *Verify:* `uv run pytest` passes.
- [ ] **T-21** Quality tooling — Ruff (lint + format), `mypy --strict`, `import-linter` contracts (ADR-024).
  *Verify:* `ruff check`, `ruff format --check`, `mypy`, `lint-imports` all pass.
- [ ] **T-22** Export the generated OpenAPI spec to `backend/openapi/openapi.json` (ADR-026) with a drift-check script.
  *Verify:* generation script writes the file; re-running produces no diff.

## Group D — Frontend Foundation (Angular 22 + Nx)

- [ ] **T-23** Generate the Nx workspace at `frontend/` with the Angular 22 `dashboard` application.
  *Verify:* `npx nx build dashboard` succeeds; installed Angular major is 22.
- [ ] **T-24** TypeScript strict mode + Nx module-boundary ESLint rules (ADR-018).
  *Verify:* `npx nx lint dashboard` passes; `strict: true` present in tsconfig.
- [ ] **T-25** Design-token source of truth: `design-tokens/tokens.json` (primitive → semantic → component) per `docs/ui/09-design-tokens.md`.
  *Verify:* JSON parses; all three tiers present; no raw hex outside the primitive tier.
- [ ] **T-26** Token generator script → CSS custom properties, TypeScript constants, Dart constants.
  *Verify:* `node scripts/generate-tokens.mjs` produces all three outputs; re-run is idempotent.
- [ ] **T-27** `shared/design-tokens` library: generated CSS, three themes (light/dark/high-contrast), theme service.
  *Verify:* unit test asserts the theme service switches themes and persists the choice.
- [ ] **T-28** Tailwind CSS v4 wired to the tokens; Angular Material + CDK installed and themed.
  *Verify:* build succeeds; a `@theme` block referencing token variables is present.
- [ ] **T-29** `shared/util`, `shared/data-access`, `shared/ui` library scaffolds.
  *Verify:* `npx nx build` succeeds for each library.
- [ ] **T-30** RFC 7807 HTTP interceptor + typed application-error model in `shared/data-access` (ADR-021).
  *Verify:* unit test maps a `problem+json` body to the typed error.
- [ ] **T-31** AG Grid wrapper foundation in `shared/ui` (ADR-020) — application-defined column contract, licence seam documented.
  *Verify:* unit test renders the wrapper; no AG Grid import exists outside `shared/ui`.
- [ ] **T-32** App shell: layout, navigation, routing foundation, theme toggle. **No business pages.**
  *Verify:* `npx nx build dashboard` succeeds; route config contains no domain route.
- [ ] **T-33** Jest configured and passing.
  *Verify:* `npx nx test dashboard` passes.
- [ ] **T-34** Playwright e2e foundation — one smoke test that the shell loads.
  *Verify:* `npx nx e2e dashboard-e2e` passes.
- [ ] **T-35** Storybook foundation.
  *Verify:* `npx nx build-storybook shared-ui` succeeds.
- [ ] **T-36** Prettier + ESLint configuration consistent across the workspace.
  *Verify:* `npx prettier --check .` and `npx nx run-many -t lint` pass.

## Group E — Flutter Foundation

- [ ] **T-37** Melos workspace at `mobile/` with `apps/` and `packages/` layout per `05-mobile-architecture.md` §8.
  *Verify:* `melos bootstrap` (or `dart pub get` per package) succeeds.
- [ ] **T-38** `packages/core` — shared constants, result types, failure model.
  *Verify:* `dart analyze` passes.
- [ ] **T-39** `packages/design_system` — generated Dart tokens + `ThemeExtension`, three themes.
  *Verify:* `flutter test` passes for the package; tokens match `tokens.json`.
- [ ] **T-40** `packages/local_storage` — Drift foundation, encrypted-at-rest seam. **No sync engine.**
  *Verify:* `flutter test` passes; database opens and closes cleanly.
- [ ] **T-41** `apps/customer_app` shell — Riverpod, go_router, theme wired. No business screens.
  *Verify:* `flutter build apk --debug` or `flutter analyze` passes; widget smoke test passes.
- [ ] **T-42** `apps/driver_app` shell — same, structured for offline-first but **without** sync implementation.
  *Verify:* same as T-41.

## Group F — Scripts, CI, Documentation

- [ ] **T-43** Development scripts: setup, dev-up/down, test, lint, format, check.
  *Verify:* each script runs and exits 0 on a clean tree.
- [ ] **T-44** GitHub Actions: `backend-ci.yml`, `frontend-ci.yml`, `mobile-ci.yml`, `repo-ci.yml` — validation only, path-filtered.
  *Verify:* YAML parses; every step has a locally-runnable equivalent in `scripts/`.
- [ ] **T-45** `CONTRIBUTING.md` — workflow, standards, commit conventions, the one-feature-at-a-time rule.
  *Verify:* file exists; links resolve.
- [ ] **T-46** Update `README.md` with prerequisites and every run/test/lint/format command.
  *Verify:* every command listed has been executed successfully at least once.
- [ ] **T-47** Update `planning/current_phase.md` and `knowledge/12-current-status.md`.
  *Verify:* both reflect the actual post-Phase-1 state.

## Group G — Verification & Closeout

- [ ] **T-48** Full local CI-equivalent run across all three stacks.
  *Verify:* `scripts/check.sh` exits 0.
- [ ] **T-49** Confirm no business feature exists.
  *Verify:* grep for domain nouns (customer, order, inventory, delivery, invoice, ledger) in source returns only token/config/doc noise.
- [ ] **T-50** Git: initial commit.
  *Verify:* `git log --oneline` shows the commit; `git status` clean.
- [ ] **T-51** Update `STATUS.md` to Complete.
- [-] **T-52** Start Phase 2. **Not done — deliberately.** Instruction: "Do NOT automatically start Authentication."

---

## Discovered Work

Recorded, not implemented — per `AGENTS.md` §Scope Control.

| ID | Item | Status |
|---|---|---|
| DW-11 | *(populated during implementation)* | |
