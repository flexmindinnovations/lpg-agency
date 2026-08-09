# STATUS — Phase 1: Repository / Development Foundation

**Feature:** 01-repository-foundation
**Plan:** [PLAN.md](./PLAN.md) · **Tasks:** [TASKS.md](./TASKS.md)

---

## Status

**COMPLETE — with one verification blocked on credentials that have not been supplied**

Every Phase 1 deliverable is built and verified by running the command, not by inspecting generated files. The five Docker-blocked verifications from the previous session are now **closed**. One new item is blocked: a live connection to **Supabase** PostgreSQL, because those credentials were not provided.

## Progress

**58 / 60 actionable tasks complete (97%)** · 2 blocked · 2 intentionally not done

| Group | Description | Complete | State |
|---|---|---|---|
| A | Repository skeleton & Git | 4/4 | ✅ Verified |
| B | **Local development environment** | **4/4** | ✅ **Verified — was 3/4** |
| C | **Backend foundation (FastAPI)** | **14/14** | ✅ **Verified — was 11/14** |
| D | Frontend foundation (Angular 22 + Nx) | 12/14 | ✅ Verified (2 deferred/blocked, unchanged) |
| E | Flutter foundation | 6/6 | ✅ Verified |
| F | Scripts, CI, documentation | 5/5 | ✅ Verified |
| G | Verification & closeout | 4/4 | ✅ Verified |
| H | **Phase 1 close-out (new)** | **9/10** | ⚠️ 1 blocked on Supabase credentials |

---

## Previously Blocked — Now Verified

Docker Desktop started this session, which closed all five.

| Task | Evidence |
|---|---|
| **T-08** Environment health | Both containers healthy · `pg_isready` accepting · `redis-cli ping` → PONG · `lpg_dev` + `lpg_test` created · `pgcrypto`/`citext`/`pg_trgm` installed · **`lpg_app` confirmed `super=false bypassrls=false`** · `app.current_tenant_id` defaults empty (fail-closed) |
| **T-15** Database foundation | **15 integration tests** against real PostgreSQL 17 |
| **T-16** Redis foundation | **6 integration tests** against real Redis 7 |
| **T-19** Alembic | `current`, `heads`, `history`, `upgrade head` all run against the live database; `alembic_version` created; offline `--sql` also works |
| **Readiness endpoint** | `/health/ready` → **200 `"status":"ready"`** with both dependencies healthy — the first time it has reported ready |

---

## The Bug the Integration Tests Found

Worth calling out, because it is the reason integration tests against a real database are not optional.

`Database.session()` issued:

```sql
SET LOCAL app.current_tenant_id = :tenant_id
```

**PostgreSQL's `SET` command does not accept bind parameters.** The placeholder is a syntax error. This is the single line the entire Row-Level Security backstop depends on (ADR-017), and it would have failed the moment Phase 2 ran its first tenant-scoped query — after the schema, repositories and Unit of Work had all been built on top of it.

Replaced with:

```sql
SELECT set_config('app.current_tenant_id', :tenant_id, true)
```

Transaction-scoped (identical semantics to `SET LOCAL`), parameter-safe so the value can never be interpolated into SQL, and compatible with transaction-mode pooling — which matters now that Supabase's Supavisor is in the picture.

A second finding from the same run: the application role correctly **cannot** `CREATE TABLE`. My first draft of the rollback test assumed it could. The least-privilege grant was right and the test was wrong.

---

## Verification Results

Every figure below came from running the command.

### Backend — Python 3.13.5 / FastAPI

| Check | Result |
|---|---|
| `ruff check` | ✅ All checks passed |
| `ruff format --check` | ✅ 41 files |
| `mypy --strict` | ✅ 38 source files |
| `lint-imports` | ✅ **5 contracts kept, 0 broken** |
| `pytest` | ✅ **76 passed** (55 unit + 21 integration) |
| OpenAPI drift | ✅ Committed spec matches generated |
| Alembic (live) | ✅ connects, inspects state, upgrades |
| `/health/live` | ✅ 200, correlation ID echoed |
| `/health/ready` | ✅ **200 `ready`**, both dependencies healthy |
| Problem Details | ✅ `application/problem+json` on unknown route |

### Frontend — Angular 22.0.8 / Nx 23.1.1

| Check | Result |
|---|---|
| `prettier --check` | ✅ |
| `nx lint` (all) | ✅ 6 projects — includes module boundaries |
| `nx test` (all) | ✅ 5 projects, 14 tests |
| `nx build` (all) | ✅ |

Frontend was not modified this session beyond verification.

### Mobile — Flutter 3.44.2

All five packages: `dart format --set-exit-if-changed` ✅ · `flutter analyze` ✅ · `flutter test` ✅ (12 tests). Not modified this session.

### Repository

| Check | Result |
|---|---|
| Architecture consistency | ✅ **271 files scanned, 0 superseded-architecture instructions** |
| Markdown link integrity | ✅ 133 files, **0 broken links**, 0 references to missing files |
| Design token drift | ✅ |
| Workflow YAML | ✅ 4 workflows valid |
| `.env` tracked | ✅ None |
| `service_role` key committed | ✅ None |
| `supabase/migrations/` absent | ✅ Alembic is sole schema owner |

**Total: 102 tests passing** (76 backend + 14 frontend + 12 Flutter).

---

## Still Blocked

| Task | Why | To close |
|---|---|---|
| **T-63** Live SQLAlchemy/Alembic connection to **Supabase** PostgreSQL | Supabase database credentials were not supplied. They were described as coming separately and have not arrived. | Provide a connection string; put it in `backend/.env` (git-ignored), not in a message. Then `uv run pytest -m integration` against it. |
| **T-34** Playwright e2e execution | Browser binaries not downloaded (`npx playwright install`). Unchanged from previous session. | Phase 4 |

**On T-63, precisely what is and is not verified:** the configuration is written and its loading is unit-tested (6 tests covering the separate migration URL, the pooler statement-cache setting, and a Supabase-style pooler DSN). The Supabase MCP confirms the *project* is reachable — `ayqphthelemlnbtnknkp`, zero tables, zero migrations. That is **not** a verified SQLAlchemy connection and is not being claimed as one.

---

## Intentionally Not Done

| Task | Reason |
|---|---|
| T-35 Storybook | Deferred to Phase 4, where `shared/ui` gains components worth documenting |
| T-52 Start Phase 2 | Explicit instruction — Phase 2 remains NOT STARTED |

---

## Known Issues

1. **Supabase live connectivity unverified** (T-63) — see above.
2. **AG Grid runs on Community, not Enterprise** — licence procurement unconfirmed (DW-08). Unchanged.
3. **Supabase application role not provisioned** (DW-19) — the hosted database has only Supabase's built-in roles. Role creation is administrative, not schema, so it cannot go through Alembic. The local init SQL is the reference.
4. **Three documented mobile packages not created** — `api_client`, `auth`, `sync_engine` (DW-17). No content until Phase 6 / Phase 11.

---

## Next

**Phase 2 — Backend Foundation. NOT STARTED.**

Awaiting explicit instruction.

## Last Updated

2026-08-09
