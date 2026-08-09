# STATUS — Phase 2: Backend Foundation

**Feature:** 02-backend-foundation
**Plan:** [PLAN.md](./PLAN.md) · **Tasks:** [TASKS.md](./TASKS.md)

---

## Status

**COMPLETE — 34/34 tracked tasks verified.** Started and finished 2026-08-09, in a single continuous session, on explicit instruction. Every task was implemented, tested against real local PostgreSQL/Redis, and re-verified — never marked complete from code inspection alone.

---

## Final Verification (2026-08-09)

Every number below came from a command run fresh at phase close-out, after all 34 tasks.

### Backend — Python 3.13.5 / FastAPI

| Check | Result |
|---|---|
| `ruff check` | ✅ All checks passed (88 files) |
| `ruff format --check` | ✅ 88 files formatted |
| `mypy --strict` | ✅ 82 source files, 0 issues |
| `import-linter` | ✅ **5 contracts kept, 0 broken** (80 files, 198 dependencies) |
| `pytest` | ✅ **182 passed**, 0 skipped, 0 failed — up from 83 at Phase 1 close |
| OpenAPI drift | ✅ `openapi.json matches generated output` — no drift (Phase 2 added no routers) |
| Alembic, local `lpg_dev` / `lpg_uat` / `lpg_test` | ✅ 3 new migrations applied cleanly, idempotent on re-run |
| Architecture consistency | ✅ 275 files scanned, 0 findings |
| `.env` tracked | ✅ None |

### Frontend — Angular 22.0.8 / Nx 23.1.1 (regression only — untouched this phase)

| Check | Result |
|---|---|
| `nx run-many --target=lint,test,build --all --skip-nx-cache` | ✅ 6 projects, 36 tests |
| Design token drift (`generate-tokens.mjs --check`) | ✅ No drift |

Confirms ADR-028 (PrimeNG/AG Grid hybrid, decided the same day, prior session) remains valid and completely untouched by this backend-only phase.

### Mobile — Flutter 3.44.2 (regression only — untouched this phase)

`melos` is not installed in this environment; `flutter analyze` + `flutter test` run directly per package, matching `scripts/test.sh`'s own established pattern (which also bypasses melos). All 5 packages (`core`, `design_system`, `local_storage`, `customer_app`, `driver_app`) analyze clean. **12/12 tests pass** — exactly matching Phase 1's baseline, confirming zero regression.

**Total: 230 tests passing** (182 backend + 36 frontend + 12 Flutter) — up from 131 at Phase 1 close.

---

## What Was Built

Full detail and verification notes per task: [TASKS.md](./TASKS.md). Summary by area:

| Area | Delivered |
|---|---|
| A — Database Foundation | DEV/UAT/PROD configuration verified (9 new tests), local role/extension state confirmed, `backend/.env`-points-at-PROD risk documented and worked around throughout |
| B — Tenant Context | `TenantResolver` protocol, interim `HeaderTenantResolver` (not a security boundary), `get_tenant_context`/`get_unit_of_work` FastAPI dependencies |
| C — Unit of Work | `SqlAlchemyUnitOfWork` — commit/rollback (both idempotent, both context-manager-compatible), event collection, `Database.open_session()` (no auto-commit, for the UoW to own exclusively) |
| D — Repository | `TenantRepository` port + `SqlAlchemyTenantRepository`, built on the `Tenant` aggregate introduced for the RLS proof — not a business feature |
| E — CQRS | `Command`/`Query` markers, `RenameTenantCommand`/`RenameTenantUseCase` — the one illustrative example, end to end |
| F — Domain Events | `DomainEventDispatcher`, wired into `SqlAlchemyUnitOfWork.commit()`, dispatched only after a successful commit |
| G — Background Worker | **ADR-029: ARQ selected**, resolving ADR-023/DW-06. Worker entry point, job contract, `JobQueue` (enqueue side), health check |
| H — Redis Infrastructure | `RedisCacheClient` implementing the existing `CacheClient` port. No pub/sub helper built — reconsidered as unnecessary (see TASKS.md Area H) |
| I — Idempotency | `IdempotencyService` — claim/execute/replay via Redis `SET NX`, order-independent fingerprinting, all four required scenarios tested including 5-way concurrency |
| J — Rate Limiting | `RateLimiter` — atomic fixed-window counter, `.check()`/`.enforce()`, not wired to any endpoint |
| K — Error Architecture | Audited; nothing missing. New exception types plug into existing generic handlers with zero new handler code |
| L — Observability | **Real gap found and closed**: `tenant_id`/`user_id` were never bound to structured logs. Fixed in `get_tenant_context` |
| M — Audit Foundation | `audit.audit_log` (migration `40065f2b4dc3`) + `AuditRecorder` — a generic SQLAlchemy `before_flush` hook, works for any future ORM model with no per-model code. Database-enforced immutability proven directly |
| N — Database Extensions | Migration `574dc291c82c` — `citext`/`pg_trgm`, idempotent, applied locally, **not** applied to Supabase PROD |
| O — Tenant Schema + RLS | Migration `0242df1a3871` — `tenant.tenant`, self-referential RLS. New dedicated `tests/tenant_isolation/` suite, 8 tests, both directions, positive controls |
| P–T | Full-suite re-verification, OpenAPI check, frontend/mobile regression, documentation sync — all in this file and `TASKS.md` |

---

## Real Findings This Phase (not just a pass/fail)

1. **`backend/.env` currently on disk is half-configured for PROD** — `LPG_ENVIRONMENT=production`, real Supabase host/credential, but empty `LPG_REDIS_URL`/`LPG_MIGRATION_DATABASE_URL`. Importing `lpg.api.app` or `lpg.infrastructure.jobs.worker` directly with this file as-is crashes at startup on a Pydantic validation error — a real, currently-live footgun for the next person who runs `uvicorn` or `arq` locally without fixing it first. Not touched (it's the user's own file); documented prominently instead.
2. **A raw-session API dependency would have leaked SQLAlchemy into the API layer** — caught immediately by `import-linter`, not by review. Redesigned to `get_unit_of_work` returning the `UnitOfWork` port, matching `03-backend-architecture.md` §3.2's own illustrative shape exactly.
3. **`Database.session()` and a new `UnitOfWork` would have double-managed the same transaction** — found while wiring `get_unit_of_work`, before it ever reached a test. Fixed by adding `Database.open_session()` (no auto-commit), leaving `session()` unchanged for its existing Phase 1 callers.
4. **`tenant.tenant`'s RLS design makes tenant self-registration through the app role structurally impossible** — not a bug, a consequence of the self-referential policy correctly matching "tenant provisioning is a platform/admin operation." Confirmed by design, not accidentally discovered — but confirmed the illustrative repository could only demonstrate read/update, not create, and the RLS isolation suite must seed via the elevated role.
5. **Structured logs never carried `tenant_id`/`user_id`**, contradicting `03-backend-architecture.md` §10's own stated contract. Real gap, closed in Area L.
6. **Adding `arq` downgraded `redis` from 8.1.0 → 5.3.1** (arq pins `redis<6`), which broke `mypy --strict` at three call sites due to less-complete redis-py 5.x stubs. Fixed with narrow, documented `type: ignore`s pinned to the version gap.
7. ~~`docs/data/18-error-catalog.md` predates and mismatches the actual implemented error codes~~ (DW-23) — **resolved same day**, in a dedicated follow-up pass explicitly requested by the user. See `docs/data/18-error-catalog.md`'s own "Reconciled 2026-08-09" section for the three naming fixes and one description fix found.

---

## Migrations Applied

| Revision | Purpose | DEV | UAT | Test | Supabase PROD |
|---|---|---|---|---|---|
| `574dc291c82c` | `citext`/`pg_trgm` extensions | ✅ | ✅ | ✅ | ✅ applied 2026-08-09 |
| `0242df1a3871` | `tenant.tenant` + self-referential RLS | ✅ | ✅ | ✅ | ✅ applied 2026-08-09 |
| `40065f2b4dc3` | `audit.audit_log` + RLS + immutability | ✅ | ✅ | ✅ | ✅ applied 2026-08-09 |

Per-database role resolution (`lpg_app` vs `lpg_app_uat`) is handled inside each migration via `current_database()`. On Supabase PROD, once `lpg_app` was provisioned (DW-19) and `alembic upgrade head` run against the superuser migration URL, both migrations' grant logic self-applied correctly with **no changes needed** — exactly as designed: `lpg_app` received `SELECT, UPDATE, DELETE` on `tenant.tenant` and `SELECT, INSERT` on `audit.audit_log`, verified via `information_schema.role_table_grants`.

**Incident during DW-19, self-corrected within the same session:** the local-dev role-provisioning pattern (`REVOKE CONNECT ... FROM PUBLIC`, appropriate where `lpg_dev`/`lpg_uat`/`lpg_test` are separate databases) is wrong on Supabase, where `postgres` is the one shared database other Supabase-internal service roles also depend on without an explicit grant. Running it broke the Supabase Management API/MCP tool's own connectivity briefly; caught immediately by a failed verification call and reverted (`GRANT CONNECT ... TO PUBLIC`) before any migration or application traffic was affected — no tenant data existed yet at that point in the session.

**A second finding, unrelated to DW-19/20, closed the same session:** Supabase's security linter flagged `public.alembic_version` (auto-exposed to the anon API by PostgREST, which this project does not use per ADR-027) as having RLS disabled. Enabled RLS with no policies — the correct deny-all posture for a table nobody should query over REST.

---

## Still Open (not blockers, not attempted this phase)

- ~~DW-19~~ — **resolved 2026-08-09.** `lpg_app` provisioned on Supabase (`NOSUPERUSER`/`NOBYPASSRLS`), application connection switched to it.
- ~~DW-20~~ — **resolved 2026-08-09.** `citext`/`pg_trgm` installed on Supabase PROD via `alembic upgrade head`.
- ~~DW-22~~ — **resolved 2026-08-09.** PrimeNG licence-tier eligibility (frontend, prior session) — product owner confirmed fewer than 5 developers and $0 annual revenue, comfortably within PrimeTek's Community-tier thresholds. See `planning/current_phase.md`.
- ~~DW-23~~ — resolved (see above).
- **DW-12** — mandatory (non-optional) tenant-scoped session. Correctly still open: genuinely depends on Authentication (Phase 6) for a real JWT.
- Real-time publisher (`RealtimePublisher` port, ADR-015) has no implementation yet — Phase 3+ scope, not attempted.
- No business job exists — only the ARQ worker skeleton and one infrastructure-proof `ping` job.

---

## Next

Await explicit instruction. Recommended: **Phase 6 — Authentication & Authorization**, since it is what Phase 2's `HeaderTenantResolver` and DW-12 exist to be replaced by, and it unlocks the first real business-facing endpoints.

## Last Updated

2026-08-09 — phase complete. Same-day follow-up: DW-19 and DW-20 resolved (Supabase `lpg_app` role provisioned, all three migrations applied to Supabase PROD) — see "Still Open" above and `planning/current_phase.md`.
