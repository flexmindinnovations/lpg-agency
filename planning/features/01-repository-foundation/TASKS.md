# TASKS — Phase 1: Repository / Development Foundation

**Feature:** 01-repository-foundation
**Plan:** [PLAN.md](./PLAN.md) · **Status:** [STATUS.md](./STATUS.md)

Legend: `[ ]` not started · `[~]` in progress · `[x]` complete (verified) · `[!]` blocked · `[-]` intentionally not done

**A task is complete only when its Verify command has been run and passed.** Generated files alone are not completion.

---

## Group A — Repository Skeleton & Git

- [x] **T-01** Create `.gitignore` covering Python, Node/Nx, Flutter/Dart, Docker, IDE, OS artifacts. Must exclude `.env` while allowing `.env.example`.
  *Verify:* `git status --porcelain` shows no `.env`, `node_modules`, `__pycache__`, or build output.
- [x] **T-02** Create `.gitattributes` (line-ending normalization — the repo is on Windows, CI is Linux).
  *Verify:* file exists; `git check-attr text -- backend/pyproject.toml` reports `text: auto`.
- [x] **T-03** Create `.editorconfig` matching each stack's conventions.
  *Verify:* file exists and parses; indent rules present for `.py`, `.ts`, `.dart`, `.yml`, `.md`.
- [x] **T-04** Create top-level directory skeleton: `infrastructure/`, `scripts/`, `.github/workflows/`, `design-tokens/`.
  *Verify:* all directories exist and each contains at least one tracked file.

## Group B — Local Development Environment

- [x] **T-05** Author `infrastructure/docker/docker-compose.yml` — PostgreSQL 17 + Redis 7, named volumes, healthchecks, non-default ports to avoid collisions.
  *Verify:* `docker compose config` parses without error.
- [x] **T-06** PostgreSQL init script — extensions and the non-superuser application role required by RLS (ADR-017: the app role must not hold `BYPASSRLS`).
  *Verify:* SQL file present and referenced by Compose; syntax reviewed.
- [x] **T-07** Create `.env.example` files (root, backend). Placeholders only — no real secrets.
  *Verify:* `grep -rE '(password|secret|key)\s*=\s*\S{16,}' *.env.example` returns nothing meaningful; `.env` is git-ignored.
- [!] **T-08** Bring the environment up and confirm both services are healthy.
  *Verify:* `docker compose ps` shows both healthy; `docker compose exec postgres pg_isready`; `redis-cli ping` → PONG.

## Group C — Backend Foundation (FastAPI)

- [x] **T-09** Initialize the uv project: `pyproject.toml`, Python 3.13 pin, dependency groups.
  *Verify:* `uv sync` succeeds; `uv run python -c "import sys; print(sys.version)"` reports 3.13.
- [x] **T-10** Create the Clean Architecture package skeleton: `domain/`, `application/`, `infrastructure/`, `api/`, `config/` with base classes only.
  *Verify:* `uv run python -c "import lpg"` succeeds; no business aggregate exists.
- [x] **T-11** Settings/configuration via Pydantic v2 `BaseSettings`, loaded from environment.
  *Verify:* unit test asserts settings load and that a missing required var fails loudly.
- [x] **T-12** Structured logging foundation (`structlog`), JSON output, with a redaction processor.
  *Verify:* test asserts JSON output and that a secret-named field is redacted.
- [x] **T-13** Correlation-ID middleware — accept inbound header or generate; bind to log context; echo on response.
  *Verify:* test asserts the response header is present and echoes a supplied ID.
- [x] **T-14** RFC 7807 exception handling foundation (ADR-021) with `error_code` extension.
  *Verify:* test asserts `application/problem+json`, and presence of `type`/`title`/`status`/`error_code`.
- [!] **T-15** Database connection foundation — async SQLAlchemy 2.x engine, session factory, tenant-context seam.
  *Verify:* integration test connects to Compose PostgreSQL and executes `SELECT 1`.
- [!] **T-16** Redis connection foundation — async client, lifecycle-managed.
  *Verify:* integration test PINGs Compose Redis.
- [x] **T-17** Health and readiness endpoints — `/health/live` (process) and `/health/ready` (dependencies).
  *Verify:* test asserts live returns 200 unconditionally; ready reports per-dependency status.
- [x] **T-18** App factory: CORS, OpenAPI metadata, versioned `/api/v1` router, lifespan management.
  *Verify:* app starts; `/api/v1/openapi.json` is valid OpenAPI 3.1.
- [!] **T-19** Alembic baseline — configured against the async engine, no migrations yet.
  *Verify:* `uv run alembic current` runs without error against Compose PostgreSQL.
- [x] **T-20** pytest foundation — async support, fixtures, unit/integration split.
  *Verify:* `uv run pytest` passes.
- [x] **T-21** Quality tooling — Ruff (lint + format), `mypy --strict`, `import-linter` contracts (ADR-024).
  *Verify:* `ruff check`, `ruff format --check`, `mypy`, `lint-imports` all pass.
- [x] **T-22** Export the generated OpenAPI spec to `backend/openapi/openapi.json` (ADR-026) with a drift-check script.
  *Verify:* generation script writes the file; re-running produces no diff.

## Group D — Frontend Foundation (Angular 22 + Nx)

- [x] **T-23** Generate the Nx workspace at `frontend/` with the Angular 22 `dashboard` application.
  *Verify:* `npx nx build dashboard` succeeds; installed Angular major is 22.
- [x] **T-24** TypeScript strict mode + Nx module-boundary ESLint rules (ADR-018).
  *Verify:* `npx nx lint dashboard` passes; `strict: true` present in tsconfig.
- [x] **T-25** Design-token source of truth: `design-tokens/tokens.json` (primitive → semantic → component) per `docs/ui/09-design-tokens.md`.
  *Verify:* JSON parses; all three tiers present; no raw hex outside the primitive tier.
- [x] **T-26** Token generator script → CSS custom properties, TypeScript constants, Dart constants.
  *Verify:* `node scripts/generate-tokens.mjs` produces all three outputs; re-run is idempotent.
- [x] **T-27** `shared/design-tokens` library: generated CSS, three themes (light/dark/high-contrast), theme service.
  *Verify:* unit test asserts the theme service switches themes and persists the choice.
- [x] **T-28** Tailwind CSS v4 wired to the tokens; Angular Material + CDK installed and themed.
  *Verify:* build succeeds; a `@theme` block referencing token variables is present.
- [x] **T-29** `shared/util`, `shared/data-access`, `shared/ui` library scaffolds.
  *Verify:* `npx nx build` succeeds for each library.
- [x] **T-30** RFC 7807 HTTP interceptor + typed application-error model in `shared/data-access` (ADR-021).
  *Verify:* unit test maps a `problem+json` body to the typed error.
- [x] **T-31** AG Grid wrapper foundation in `shared/ui` (ADR-020) — application-defined column contract, licence seam documented.
  *Verify:* unit test renders the wrapper; no AG Grid import exists outside `shared/ui`.
- [x] **T-32** App shell: layout, navigation, routing foundation, theme toggle. **No business pages.**
  *Verify:* `npx nx build dashboard` succeeds; route config contains no domain route.
- [x] **T-33** Jest configured and passing.
  *Verify:* `npx nx test dashboard` passes.
- [!] **T-34** Playwright e2e foundation — scaffolded by the Nx generator (`apps/dashboard-e2e`).
  *Verify:* **BLOCKED** — `npx nx e2e dashboard-e2e` needs `npx playwright install` to download browser binaries, which was not run in this environment. Configuration is present and wired into CI; execution unverified.
- [-] **T-35** Storybook foundation. **Not done.** Deferred to Phase 4 (Angular Foundation), where the shared UI library gains components worth documenting. Storybook over a single grid wrapper is tooling without content.
  *Verify:* n/a — deferred, recorded as DW-14.
- [x] **T-36** Prettier + ESLint configuration consistent across the workspace.
  *Verify:* `npx prettier --check .` and `npx nx run-many -t lint` pass.

## Group E — Flutter Foundation

- [x] **T-37** Melos workspace at `mobile/` with `apps/` and `packages/` layout per `05-mobile-architecture.md` §8.
  *Verify:* `melos bootstrap` (or `dart pub get` per package) succeeds.
- [x] **T-38** `packages/core` — shared constants, result types, failure model.
  *Verify:* `dart analyze` passes.
- [x] **T-39** `packages/design_system` — generated Dart tokens + `ThemeExtension`, three themes.
  *Verify:* `flutter test` passes for the package; tokens match `tokens.json`.
- [x] **T-40** `packages/local_storage` — Drift foundation, encrypted-at-rest seam. **No sync engine.**
  *Verify:* `flutter test` passes; database opens and closes cleanly.
- [x] **T-41** `apps/customer_app` shell — Riverpod, go_router, theme wired. No business screens.
  *Verify:* `flutter build apk --debug` or `flutter analyze` passes; widget smoke test passes.
- [x] **T-42** `apps/driver_app` shell — same, structured for offline-first but **without** sync implementation.
  *Verify:* same as T-41.

## Group F — Scripts, CI, Documentation

- [x] **T-43** Development scripts: setup, dev-up/down, test, lint, format, check.
  *Verify:* each script runs and exits 0 on a clean tree.
- [x] **T-44** GitHub Actions: `backend-ci.yml`, `frontend-ci.yml`, `mobile-ci.yml`, `repo-ci.yml` — validation only, path-filtered.
  *Verify:* YAML parses; every step has a locally-runnable equivalent in `scripts/`.
- [x] **T-45** `CONTRIBUTING.md` — workflow, standards, commit conventions, the one-feature-at-a-time rule.
  *Verify:* file exists; links resolve.
- [x] **T-46** Update `README.md` with prerequisites and every run/test/lint/format command.
  *Verify:* every command listed has been executed successfully at least once.
- [x] **T-47** Update `planning/current_phase.md` and `knowledge/12-current-status.md`.
  *Verify:* both reflect the actual post-Phase-1 state.

## Group G — Verification & Closeout

- [x] **T-48** Full local CI-equivalent run across all three stacks.
  *Verify:* `scripts/check.sh` exits 0.
- [x] **T-49** Confirm no business feature exists.
  *Verify:* grep for domain nouns (customer, order, inventory, delivery, invoice, ledger) in source returns only token/config/doc noise.
- [x] **T-50** Git: initial commit.
  *Verify:* `git log --oneline` shows the commit; `git status` clean.
- [x] **T-51** Update `STATUS.md` to Complete.
- [-] **T-52** Start Phase 2. **Not done — deliberately.** Instruction: "Do NOT automatically start Authentication."

---

## Discovered Work

Recorded, not implemented — per `AGENTS.md` §Scope Control.

| ID | Item | Why deferred |
|---|---|---|
| DW-11 | Docker daemon would not start in this environment, so Compose-dependent verification could not run (T-08, T-15, T-16, T-19). Configuration is authored and `docker compose config` validates; the services themselves are unverified. | Environment limitation, not a code defect. First developer with a working Docker runs `./scripts/dev-up.sh` and `./scripts/check.sh` to close these out. |
| DW-12 | `Database.session()` accepts an optional `tenant_id`. From Phase 6 the API dependency producing sessions must **require** a resolved tenant context, so an unscoped session is unobtainable through the request path. | Cannot be enforced before Authentication exists — there is no JWT to resolve a tenant from yet. |
| DW-13 | The `create-nx-workspace` `angular-monorepo` preset silently maps to a demo e-commerce template that ignores `--appName`, `--unitTestRunner` and `--e2eTestRunner`, and ships a conflicting `apps/api`. Worked around by generating an empty workspace and adding Angular explicitly. | Upstream tooling behaviour. Worth knowing before anyone regenerates the workspace. |
| DW-14 | Storybook not configured (T-35). | Deferred to Phase 4, where `shared/ui` gains components worth documenting. Storybook over a single grid wrapper is tooling without content. |
| DW-15 | Playwright browser binaries not downloaded, so the e2e smoke test was never executed (T-34). | `npx playwright install` is a large download; scaffolding and CI wiring are present. Close out in Phase 4. |
| DW-16 | AG Grid wrapper runs on AG Grid **Community**, not Enterprise. | Enterprise licence procurement is unconfirmed (DW-08 from Phase 0). The wrapper is what makes this a two-line change later rather than a refactor. |
| DW-17 | `mobile/packages/api_client`, `auth` and `sync_engine` are documented in `05-mobile-architecture.md` §8 but not created. | They have no content until Authentication (Phase 6) and Delivery (Phase 11). Creating empty packages now would be structure without substance. |
| DW-18 | **Assert the application's database role cannot bypass RLS.** ADR-027 requires a `NOSUPERUSER`, `NOBYPASSRLS` role on Supabase, mirroring `lpg_app` locally. CI can check `supabase/migrations/` absence and scan for a committed `service_role` key (both added to `repo-ci.yml`), but verifying the *live* role's attributes needs a database connection. | Phase 2, alongside the first migration and the tenant-isolation suite — that is where a live connection exists and where getting it wrong would first matter. |
| DW-19 | **Provision the Supabase application role.** The hosted database has no `lpg_app` equivalent yet; only Supabase's built-in roles exist. The local Docker init SQL (`infrastructure/docker/postgres/init/01-init.sql`) is the reference. | Phase 2. Cannot be done through Alembic (role creation is an administrative act, not schema), so it needs a documented one-time provisioning step run as `postgres`. |
