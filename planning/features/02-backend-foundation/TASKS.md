# TASKS — Phase 2: Backend Foundation

Legend: `[ ]` not started · `[~]` in progress · `[x]` complete and verified (build+lint+types+tests all re-run, not inspected)

---

## A — Database Foundation

- [x] **T-01** Verify `Settings.effective_database_url` composition against DEV/UAT/PROD example files with a unit test per environment (extends `test_settings.py`).
  *Verify:* `pytest tests/unit/test_environment_configuration.py` — 9 passed. New file rather than extending `test_settings.py` directly, since it needed its own env-file-parsing helper.
- [x] **T-02** Confirm local Docker DEV (`lpg_dev`) and UAT (`lpg_uat`) are reachable as their application roles (`lpg_app`, `lpg_app_uat`), not the superuser.
  *Verify:* manual `asyncpg` connection check with explicit env vars (never ambient `.env`) — confirmed `lpg_app`/`lpg_app_uat`/`lpg_app` (test db) all connect as `superuser=False, bypassrls=False`. Also confirmed `citext`, `pg_trgm`, `pgcrypto` already present on both DEV and UAT (via the docker init script, not yet via Alembic — see T-24).
- [x] **T-03** Document the DEV/UAT/PROD topology and the `backend/.env`-currently-points-at-PROD finding in `STATUS.md` and `planning/current_phase.md`.
  *Verify:* both files updated; see PLAN.md's "Critical Operational Note".

## B — Tenant Context

- [x] **T-04** Add `application/common/ports.py`'s new `TenantResolver` protocol, `application/common/tenant.py`'s concrete `RequestTenantContext`, `infrastructure/tenant/header_resolver.py`'s interim `HeaderTenantResolver` (explicit request header, clearly documented as a Phase 2 stand-in — not a security boundary, not wired to any reachable endpoint), and `api/v1/dependencies/tenant.py`'s `get_tenant_context` FastAPI dependency.
  *Verify:* `tests/unit/test_tenant_resolver.py` (5 tests, no database) + `tests/integration/test_tenant_dependency_chain.py::TestGetTenantContext` (2 tests).
- [x] **T-05** Wire a tenant-scoped dependency chain. Redesigned mid-implementation from a raw-session dependency to `api/v1/dependencies/unit_of_work.py`'s `get_unit_of_work`, after discovering a raw `AsyncSession`-returning API dependency would either double-manage the transaction against `Database.session()`'s own commit/rollback, or leak SQLAlchemy types into the API layer (`import-linter` caught this immediately — see `06-database-architecture.md`/`03-backend-architecture.md` §3.2's own illustrative shape, which returns `UnitOfWork`, not a session). Added `Database.open_session()` — tenant-scoped, no auto-commit/rollback — as the seam `SqlAlchemyUnitOfWork` (Area C) wraps exclusively.
  *Verify:* `tests/integration/test_tenant_dependency_chain.py::TestGetUnitOfWork` (3 tests) + `tests/integration/test_database.py::TestOpenSession` (4 new tests).

## C — Unit of Work

- [x] **T-06** Implement `infrastructure/persistence/unit_of_work.py`: `SqlAlchemyUnitOfWork` implementing the existing `UnitOfWork` protocol — `__aenter__`/`__aexit__` (signature matches the protocol's loose `*exc_info: object` exactly, required for structural typing under `mypy --strict`), `commit()`, `rollback()` (both idempotent after the first call), `collect_events()`, plus `register_aggregate()` (not on the protocol — an infrastructure-level extension repositories use).
- [x] **T-07** Tests: commit persists, idempotent double-commit, context-manager commits on clean exit, explicit-commit-then-clean-exit doesn't double-commit, rollback discards, context-manager rolls back on exception, idempotent double-rollback, event collection (empty / gathers from every registered aggregate / untouched aggregates excluded), `.session` exposure.
  *Verify:* `tests/integration/test_unit_of_work.py` — 12 tests, all against real local Docker PostgreSQL. Placed under `tests/integration/` (not `tests/infrastructure/`) to match this repo's actual existing folder convention rather than the aspirational one in `03-backend-architecture.md` §14.

**Area A–C full verification, re-run fresh after all three areas:** `pytest` 118/118 passed · `ruff check` all checks passed · `ruff format --check` 51 files formatted · `mypy --strict` 0 issues (48 source files) · `import-linter` 5/5 contracts kept (56 files, 110 dependencies). One new `ignore_imports` entry added (`lpg.api.v1.dependencies.unit_of_work -> lpg.infrastructure.persistence.unit_of_work`), matching the existing composition-root-exception pattern exactly.

## D — Repository Architecture

- [x] **T-08** `application/tenant/ports.py`'s `TenantRepository` protocol (`get`/`save` only — no `add()`, since `tenant.tenant`'s RLS policy makes self-registration through a tenant-scoped connection structurally impossible by design, not an oversight) + `infrastructure/persistence/repositories/tenant.py`'s `SqlAlchemyTenantRepository`, using the `Tenant` aggregate (`domain/tenant/tenant.py`) introduced for the RLS proof — not a business/Tenant-Administration aggregate (no create/delete, one behaviour: `rename()`). Repository construction takes the `SqlAlchemyUnitOfWork`, not a raw session, so `get()` can call `uow.register_aggregate()`.
  *Verify:* `tests/integration/test_tenant_repository.py` — 4 tests: own row returned, another tenant's row invisible (RLS), loaded aggregate registers with the UoW, a save persists across an independent session.

## E — Application Services / CQRS

- [x] **T-09** `application/common/cqrs.py`: `Command`/`Query` marker base classes. No dispatch registry, no decorator-driven handler discovery — a use case is a plain class with `execute()`, called directly.
- [x] **T-10** `application/tenant/rename_tenant.py`: `RenameTenantCommand` + `RenameTenantUseCase`, exercising Command → Application Service → Repository → UoW → domain event end to end. No query-side example shipped — no read model exists yet to justify one, and inventing one would be exactly the "complicated CQRS framework" the instructions rule out.
  *Verify:* `tests/integration/test_rename_tenant_use_case.py` — 4 tests: renames and persists, dispatches `TenantRenamed` after commit, raises `NotFoundError` for a tenant outside RLS visibility (deliberately the same response as "doesn't exist" — no 403-vs-404 tenant-existence leak), rejects an empty name via the domain invariant.

## F — Domain Events

- [x] **T-11** `infrastructure/events/dispatcher.py`: `DomainEventDispatcher`, handler registration by exact event type (no subtype matching), a failing handler is logged and re-raised (never silently swallowed, per `AGENTS.md`'s error-handling rule) without rolling back the already-committed transaction.
- [x] **T-12** Wired into `SqlAlchemyUnitOfWork.commit()` — flush → audit (no-op until Area M) → commit → dispatch (only after `session.commit()` succeeds) → clear each tracked aggregate's events. Dispatcher is optional (constructor default `None`) so Area C's existing tests are unaffected. Wired process-wide via a new `AppState.event_dispatcher`, constructed and torn down in the lifespan exactly like `Database`/`RedisClient`.
  *Verify:* `tests/unit/test_domain_event_dispatcher.py` (8 tests, no database) + `tests/integration/test_rename_tenant_use_case.py::test_dispatches_the_domain_event_after_commit`.

**Area D–F full verification:** `pytest` 134/134 passed · `ruff check`/`ruff format --check` clean (68 files) · `mypy --strict` 0 issues (63 source files) · `import-linter` 5/5 contracts kept (68 files, 146 dependencies).

**Migrations applied this session (DEV + UAT + local `lpg_test`, not yet PROD):**
- `574dc291c82c` — `citext`/`pg_trgm` extensions (idempotent; already present locally via `01-init.sql`, this is what makes it an Alembic-owned fact rather than a Docker-only side effect, and what will actually install them on hosted Supabase when applied there).
- `0242df1a3871` — `tenant.tenant` table + RLS (self-referential: `id = current_setting('app.current_tenant_id')`, since a tenant cannot belong to another tenant). Grants resolved per-database (`lpg_app` vs `lpg_app_uat`) via `current_database()`, guarded so it no-ops safely where the target role doesn't exist yet (hosted Supabase, pending DW-19).

## G — Background Worker Foundation

- [x] **T-13** Evaluated ARQ / Dramatiq / Celery. **ARQ selected** — the deciding factor is that this entire stack is async-first (FastAPI, SQLAlchemy 2.x async, asyncpg) with zero synchronous data-access path; Dramatiq and Celery are both sync-first execution models that would force `asyncio.run()`-per-task wrapping or a second sync persistence stack, while ARQ's jobs are plain `async def` sharing the same Redis instance already committed for cache/sessions/real-time (ADR-015) — no new broker. Recorded as **ADR-029**, resolving ADR-023's deferral (DW-06 closed).
- [x] **T-14** `infrastructure/jobs/worker.py` — `WorkerSettings` (functions, startup/shutdown lifecycle connecting/disconnecting `Database`), documented job contract (tenant-scoped / idempotent / observable / retry-safe) in the module docstring, and `ping` — an infrastructure-only no-op job, not a business job. `infrastructure/jobs/pool.py` — `JobQueue`, the API-process side that enqueues work, wired into `AppState`/lifespan and a new `JobQueueHealthCheck` alongside `Database`/`Redis`. Entry-point module like `lpg.api.app` — constructs real `Settings()` at import time (ARQ's CLI needs `redis_settings` as a class attribute); every test defers the import, matching the existing `lpg.api.app` discipline.
  *Verify:* `tests/unit/test_job_queue.py` (3, pre-connect states) + `tests/integration/test_job_worker.py` (3, including a genuine enqueue → burst-mode `arq.worker.Worker` → `job.result()` round trip returning `"pong"`).

## H — Redis Infrastructure

- [x] **T-15** `infrastructure/redis/cache.py`: `RedisCacheClient` implementing the existing `CacheClient` port.
- [x] **T-16** No pub/sub helper built — reconsidered during implementation. Neither idempotency (needs atomic claim/replay) nor rate limiting (needs atomic counters) actually needs pub/sub; both are correctly built directly on `redis.asyncio.Redis`'s atomic primitives (`SET NX`, `INCR`+`EXPIRE`). Building a pub/sub helper nothing consumes would have been exactly the "unnecessary infrastructure" the instructions warn against — `RealtimePublisher` (ADR-015) remains the real pub/sub seam, untouched, for Phase 3+.
  *Verify:* `tests/integration/test_redis_cache.py` — 5 tests (get/set/delete round trip, TTL expiry, no-TTL persistence).

## I — Idempotency

- [x] **T-17** `infrastructure/idempotency/service.py`: `IdempotencyService.execute()` — `SET NX` claims the key (first writer wins), runs the operation, stores `{status: completed, fingerprint, result}` with a 24h replay TTL; a losing writer polls the same key until it flips to `completed`, then replays. `fingerprint()` is an order-independent SHA-256 over the canonicalized (sorted-keys) JSON payload. A failed first attempt deletes its own claim so a genuine retry isn't blocked by a 30s in-progress TTL. New `IdempotencyConflictError` (409) added to `application/common/errors.py`.
- [x] **T-18** `tests/integration/test_idempotency.py` — the four named scenarios plus supporting cases: first request executes once; repeated request (same fingerprint) replays without re-executing, and never crosses a tenant boundary even under a shared key string; conflicting payload (different fingerprint, same key) raises `IdempotencyConflictError`, and a *failed* first attempt correctly releases the key rather than wedging it; five concurrent identical requests (`asyncio.gather`) execute the underlying operation exactly once.
  *Verify:* 8/8 passed against real Redis.

## J — Rate Limiting Foundation

- [x] **T-19** `infrastructure/rate_limit/limiter.py`: `RateLimiter` — a fixed-window counter (`INCR` + `EXPIRE`-on-first-increment, atomic by construction since only one caller ever observes count `== 1` for a fresh key). `.check()` returns a result object; `.enforce()` raises the new `RateLimitExceededError` (429, `retry_after_seconds`) for a call site that wants to fail closed. Tenant-aware by the same `tenant:{id}:...` key convention as cache/idempotency. Not wired to any endpoint — foundation only, per the instruction not to add aggressive limits that would interfere with development.
  *Verify:* `tests/integration/test_rate_limiter.py` — 6 tests (within-limit countdown, over-limit denial with `retry_after_seconds > 0`, independent counters per key, window reset, `.enforce()` both paths).

**Area G–J full verification, and a real regression caught and fixed:** adding `arq` (which pins `redis[hiredis]<6,>=4.2.0`) downgraded the installed `redis` from 8.1.0 → 5.3.1, and redis-py 5.x's stubs are less complete — `mypy --strict` immediately caught three now-`Any`-typed call sites (`RedisClient.connect()`, `RedisCacheClient.get()`, and a pre-existing one in `tests/conftest.py`'s `redis_available` fixture). Fixed with narrow, documented `type: ignore`s pinned to the version gap, not the code. Final: `pytest` 182/182 passed · `ruff`/`mypy --strict` clean (82 source files) · `import-linter` 5/5 kept (80 files, 198 dependencies).

## K — Error Architecture

- [x] **T-20** Audited domain/application/infrastructure exception layering against Phase 2's new code paths. Found nothing missing for domain/application (the new `TenantContextMissingError`/`NotFoundError`/`InvariantViolation` usages all plug into the existing generic `application_error_handler`/`domain_error_handler` with zero new handler code — that genericity is the design working as intended). Extended `test_problem_details.py` with explicit coverage for both: a `TenantContextMissingError` route (401, stable `error_code`) and a simulated infrastructure-layer failure (raw `RuntimeError` carrying a realistic Postgres constraint-violation message) proving it falls through to the same detail-free generic 500 path — no infrastructure-specific handler exists, deliberately, since one would be the first place a leak could creep in.
  *Verify:* `tests/unit/test_problem_details.py` — grew from 17 to 22 tests (2 new routes × 2 parametrized cases + 1 dedicated leak-check test).

## L — Observability

- [x] **T-21** Verification surfaced one real gap, closed: `tenant_id`/`user_id` were not being bound to `structlog.contextvars` anywhere — only `correlation_id`/`request_path`/`request_method` (via `CorrelationIdMiddleware`) were, so `03-backend-architecture.md` §10's "every log entry carries... tenant_id, user_id" was not actually true prior to this phase. Fixed in `get_tenant_context` (`api/v1/dependencies/tenant.py`): binds both immediately after resolution, using the same `structlog.contextvars` mechanism the middleware already uses for `correlation_id` — every log for the rest of the request now carries them automatically, no call site needs to pass them explicitly. `user_id` binds as `None` (not the literal string `"None"`) when absent, matching Phase 2's no-authentication-yet reality. `SqlAlchemyUnitOfWork`'s existing debug logs (`unit_of_work_committed`, `unit_of_work_rolled_back`) and `AuditRecorder`'s (`audit_row_queued`) automatically inherit this via structlog's `merge_contextvars` processor — no per-call-site changes needed there.
  *Verify:* new `tests/unit/test_observability_seam.py` — 3 tests: `tenant_id` appears on a log emitted after `get_tenant_context` resolves, `user_id` appears when present, `user_id` renders as JSON `null` (not the string `"None"`) when absent.

**Area K–L full verification:** `pytest` 157/157 passed · `ruff`/`mypy --strict` clean · `import-linter` 5/5 kept (70 files, 164 dependencies).

## M — Audit Foundation

- [x] **T-22** Alembic migration `40065f2b4dc3` — `audit.audit_log` (tenant_id, actor_id, entity_name, entity_id, action, performed_at, correlation_id, before_state/after_state JSONB, metadata JSONB — the Phase 2 instructions' full field list, extending `06-database-architecture.md` §6 with `correlation_id`). RLS (standard tenant_id pattern, nullable for system-level rows). Application role granted `SELECT, INSERT` only — no `UPDATE`, no `DELETE`, ever.
- [x] **T-23** `infrastructure/persistence/audit.py`'s `AuditRecorder` — a SQLAlchemy `before_flush` session event listener, registered once per `SqlAlchemyUnitOfWork`. Generic by construction: inspects `session.new`/`dirty`/`deleted` for *any* ORM model (not per-model custom code), diffs changed columns via SQLAlchemy's attribute history for `before_state`, skips `AuditLogModel` itself (no recursion), reads `correlation_id` from `structlog.contextvars` (already bound by `CorrelationIdMiddleware`) rather than threading it through constructors. Fires automatically inside `commit()`'s existing `session.flush()` — no explicit call site needed anywhere.
  *Verify:* `tests/integration/test_audit_log.py` — 7 tests: exactly one row per mutation, row captures actor/tenant/action/before-after state correctly, unmodified columns excluded from the diff, a read-only transaction produces zero rows, a rolled-back transaction produces zero rows (queued row never flushed), and — the immutability proof — a direct `UPDATE`/`DELETE` against `audit.audit_log` as `lpg_app` raises `DBAPIError: permission denied`.

**Area M full verification:** `pytest` 149/149 passed · `ruff`/`mypy --strict` clean · `import-linter` 5/5 kept (70 files, 163 dependencies).

## N — Database Extensions

- [x] **T-24** Alembic migration `574dc291c82c` — idempotent `CREATE SCHEMA IF NOT EXISTS extensions` + `CREATE EXTENSION IF NOT EXISTS citext/pg_trgm SCHEMA extensions`. `pgcrypto` deliberately not touched (already core-adjacent, verified present everywhere already).
  *Verify:* applied to local DEV, UAT, and `lpg_test`; re-run confirmed idempotent (second `alembic upgrade head` is a true no-op). Verified `CREATE EXTENSION IF NOT EXISTS x SCHEMA y` is a safe no-op even when `x` already exists in a *different* schema (true locally, where `01-init.sql` originally created them in `public`). **Not applied to hosted Supabase PROD this phase** — recorded as a follow-up requiring explicit go-ahead, per the instruction to verify PROD only when explicitly safe.

## O — Tenant Schema + RLS

- [x] **T-25** Alembic migration `0242df1a3871` — `tenant.tenant` table only (`id`, `name`, `slug`, standard audit columns except `tenant_id` — a tenant cannot belong to another tenant, the same documented exception `identity.identity_user` already has — plus `version`). RLS policy created in the same migration, self-referential (`id = current_setting('app.current_tenant_id')`), `ENABLE`+`FORCE ROW LEVEL SECURITY`. Grants (`SELECT`, `UPDATE`, `DELETE` — deliberately no `INSERT`, since tenant self-registration is structurally impossible by this design and out of Phase 2's scope) resolved per-database via `current_database()`, guarded to no-op where the target role doesn't exist yet (hosted Supabase, pending DW-19).
- [x] **T-26** New `tests/tenant_isolation/` suite (a genuinely dedicated top-level folder, matching `03-backend-architecture.md` §12.1's explicit call for one — unlike the general unit/integration split, this is a distinct testing *concern*, not just an alternate taxonomy). 8 tests, raw SQL directly against the real `lpg_app` role (bypassing the repository entirely, proving the database-level backstop, not an application filter): Tenant A cannot read/modify/delete Tenant B by direct ID lookup or unfiltered `SELECT *`; positive controls prove same-tenant UPDATE/DELETE genuinely work (so the zero-rowcount results are RLS-specific, not a missing privilege or broken query); isolation holds symmetrically (B cannot touch A either); an unscoped session sees zero rows (fail-closed default).
  *Verify:* `pytest tests/tenant_isolation/` — 8/8 passed against local Docker.

**Area N–O full verification:** `pytest` 142/142 passed · `ruff`/`mypy --strict` clean · `import-linter` 5/5 kept (68 files, 146 dependencies).

## P — Testing (cross-cutting; also tracked per-area above)

- [x] **T-27** No dedicated `tests/architecture/` folder introduced — the existing `import-linter` contracts already apply generically to every module under `lpg.domain`/`lpg.application`/`lpg.api`/`lpg.infrastructure` without per-module enumeration; every module this phase added was verified against them (re-run after each area, 5/5 kept throughout, final run 80 files / 198 dependencies).
- [x] **T-28** Full backend suite re-run fresh (no cache to bypass — pytest has none) after every area, and once more at phase close-out.

## Q — OpenAPI

- [x] **T-29** `uv run python scripts/export_openapi.py --check` → `OK: openapi.json matches generated output` — no drift. Expected: Phase 2 added no routers, only internal infrastructure. Health endpoints, RFC 7807 shape, correlation ID, and `/api/v1` versioning all re-verified via the full `test_health.py`/`test_problem_details.py` suites passing.

## R — Frontend Regression

- [x] **T-30** `nx run-many --target=lint,test,build --all --skip-nx-cache` — 6 projects, all green (36 tests). `node scripts/generate-tokens.mjs --check` — no drift. Confirms ADR-028 (PrimeNG/AG Grid hybrid) remains valid and completely untouched by this backend-only phase.

## S — Mobile Regression

- [x] **T-31** `flutter analyze` + `flutter test` run directly per package (matching `scripts/test.sh`'s own established pattern — `melos` is not installed in this environment and the project's own scripts don't depend on it either). All 5 packages (`core`, `design_system`, `local_storage`, `customer_app`, `driver_app`) analyze clean; **12/12 tests pass**, exactly matching Phase 1's STATUS.md baseline — confirms zero mobile regression, as expected since Phase 2 touched no mobile code.

## T — Documentation & Close-out

- [x] **T-32** `docs/architecture/03-backend-architecture.md` — stack note updated (illustrative pseudocode is now real, tested code for UoW/repository/CQRS/events/audit); §7 Background Jobs updated to name ARQ. `06-database-architecture.md` — no update needed, it's a policy/strategy document with no "no code exists yet" caveat to correct.
- [x] **T-33** `knowledge/12-current-status.md`, `planning/current_phase.md`, and this feature's own `STATUS.md` all updated to reflect Phase 2 complete, with the recommended next phase (Phase 6 — Authentication, not the numerically-next Phase 3 — see reasoning in `STATUS.md`).
- [x] **T-34** **ADR-029** added to `docs/architecture/15-architecture-decision-records.md`, resolving ADR-023's deferral. ADR-023 itself amended with a resolution note (original text preserved verbatim below it, per project convention). Also fixed in passing: ADR-028 (from the prior session) had never been added to the ADR Summary Table — corrected alongside ADR-029's addition.

---

## Discovered Work

(Populated as found, per AGENTS.md Scope Control — recorded, not silently implemented beyond this phase's boundary.)

- **DW-23 — `docs/data/18-error-catalog.md` predated and mismatched the actual implemented `error_code` values.** Found while adding Phase 2's three new error codes. **Resolved 2026-08-09, same day, out-of-phase-scope pass explicitly requested by the user.** Reconciled line-by-line against `errors.py`/`domain/common/base.py`/`problem_details.py`: fixed three real naming mismatches (`NOT_FOUND`→`RESOURCE_NOT_FOUND`, `TOO_MANY_REQUESTS`→`RATE_LIMIT_EXCEEDED`, `INTERNAL_ERROR`→`INTERNAL_SERVER_ERROR`) and one wrong description (`VALIDATION_FAILED` was documented as "Pydantic shape validation" — that's actually the separate, previously-undocumented `REQUEST_VALIDATION_FAILED`; `VALIDATION_FAILED` is the application layer's cross-entity precondition check). Added every missing implemented code. Split the catalog into "Cross-Cutting (Implemented)" and "Business-Domain (Reserved — Not Yet Implemented)" tables so implementation status is explicit rather than requiring a source-code check. No business-domain code needed renaming — confirmed they're correctly scoped as future subclasses of the same base error hierarchy already in use. Documentation-only; no application code changed.
