# STATUS — Phase 1: Repository / Development Foundation

**Feature:** 01-repository-foundation
**Plan:** [PLAN.md](./PLAN.md) · **Tasks:** [TASKS.md](./TASKS.md)

---

## Status

**COMPLETE — with 5 environment-blocked verifications**

Every deliverable is built. Everything verifiable in this environment was verified by running the command, not by inspecting generated files. Five verifications could not be executed here and are marked **blocked**, not complete.

## Progress

**45 / 52 tasks complete (87%)** · 5 blocked · 2 intentionally not done

| Group | Description | Complete | State |
|---|---|---|---|
| A | Repository skeleton & Git | 4/4 | ✅ Verified |
| B | Local development environment | 3/4 | ⚠️ Compose authored and validated; services unverified |
| C | Backend foundation (FastAPI) | 11/14 | ⚠️ All non-DB verifications pass |
| D | Frontend foundation (Angular 22 + Nx) | 12/14 | ✅ Build, lint, test all pass |
| E | Flutter foundation | 6/6 | ✅ Verified |
| F | Scripts, CI, documentation | 5/5 | ✅ Verified |
| G | Verification & closeout | 4/4 | ✅ Verified |

## Verification Results

Every figure below came from running the command.

### Backend — Python 3.13.5 / FastAPI

| Check | Result |
|---|---|
| `uv sync` | ✅ |
| `ruff check` | ✅ All checks passed |
| `ruff format --check` | ✅ 39 files formatted |
| `mypy --strict` | ✅ No issues in 36 source files |
| `lint-imports` | ✅ **5 contracts kept, 0 broken** |
| `pytest` | ✅ **49 passed** |
| OpenAPI drift check | ✅ Committed spec matches generated |
| `alembic upgrade head --sql` | ✅ Offline mode runs |
| **Server, over HTTP** | ✅ `/health/live` → 200 with correlation ID; `/health/ready` → 503 with per-dependency detail; unknown route → `application/problem+json` |

### Frontend — Angular 22.0.8 / Nx 23.1.1

| Check | Result |
|---|---|
| `nx build` (all) | ✅ 263.89 kB initial, 72.03 kB transferred |
| `nx lint` (all) | ✅ 6 projects, 0 problems — includes module boundaries |
| `nx test` (all) | ✅ **14 passed** across 3 suites |
| `prettier --check` | ✅ |
| Token drift check | ✅ 229 CSS variables match source |

### Mobile — Flutter 3.44.2 / Dart 3.12.2

| Package | format | analyze | test |
|---|---|---|---|
| `packages/core` | ✅ | ✅ | ✅ 3 |
| `packages/design_system` | ✅ | ✅ | ✅ 4 |
| `packages/local_storage` | ✅ | ✅ | ✅ 1 |
| `apps/customer_app` | ✅ | ✅ | ✅ 2 |
| `apps/driver_app` | ✅ | ✅ | ✅ 2 |

**Total: 75 tests passing** (49 backend + 14 frontend + 12 Flutter).

### Repository

| Check | Result |
|---|---|
| `.gitignore` excludes `.env`, allows `.env.example` | ✅ Verified behaviourally |
| Line endings normalised | ✅ `git check-attr` reports `eol: lf` |
| First commit | ✅ `470436e`, 428 files, working tree clean |
| No `node_modules`/`.env`/build output staged | ✅ |
| No business feature present | ✅ Only comments describing what does not exist |
| CI workflow YAML | ✅ 4 workflows parse |

## Blocked Tasks

**Docker Desktop's daemon would not start in this environment.** Every `docker` command hung and timed out, including after an explicit launch and a 300-second poll.

| Task | What is unverified |
|---|---|
| T-08 | PostgreSQL and Redis containers actually start and report healthy |
| T-15 | Database connection against a real PostgreSQL |
| T-16 | Redis connection against a real Redis |
| T-19 | `alembic current` against a live database (offline SQL generation **does** work) |
| T-34 | Playwright e2e execution — needs `npx playwright install` for browser binaries |

What *is* verified: `docker compose config` parses; the init SQL is present and wired in; the readiness endpoint correctly reports both dependencies as unreachable with per-dependency detail, which is exactly the behaviour expected when they are down.

Closing these out is one command for a developer with a working Docker:

```bash
./scripts/dev-up.sh && ./scripts/check.sh
```

## Intentionally Not Done

| Task | Reason |
|---|---|
| T-35 Storybook | Deferred to Phase 4, where `shared/ui` gains components worth documenting. Storybook over a single grid wrapper is tooling without content. |
| T-52 Start Phase 2 | Explicit instruction: "Do NOT automatically start Authentication." |

## Known Issues

1. **Docker unavailable** — see above (DW-11).
2. **AG Grid runs on Community, not Enterprise** — licence procurement unconfirmed (DW-08 from Phase 0). The wrapper (ADR-020) is what makes enabling Enterprise a two-line change rather than a refactor.
3. **`create-nx-workspace` preset hazard** — the `angular-monorepo` preset silently maps to a demo e-commerce template, ignores the flags passed to it, and generates a conflicting `apps/api`. Worked around; recorded as DW-13 so nobody repeats it.
4. **Three documented mobile packages not created** — `api_client`, `auth`, `sync_engine` (DW-17). They have no content until Phase 6 and Phase 11.

## Deviations from the Instruction

**Flutter folder layout.** The instruction sketched `mobile/customer/` and `mobile/driver/`; the Phase 0 architecture (`05-mobile-architecture.md` §8, `14-folder-structure.md` §5) specifies `mobile/apps/customer_app/`, `mobile/apps/driver_app/` and `mobile/packages/`.

Followed the Phase 0 architecture, because the same instruction says to follow it, Dart package names must be valid identifiers, Melos expects the `apps/`+`packages/` split, and the shared-packages layer is required by the offline-first Driver App design (D-24). Both apps are still "customer" and "driver".

## Next

**Phase 2 — Backend Foundation. NOT STARTED.**

Awaiting explicit instruction, per: *"Do NOT automatically start Authentication. Wait for explicit instruction before starting Phase 2."*

## Last Updated

2026-08-09
