# STATUS — Phase 3: Shared Infrastructure (Real-Time Publisher, File Storage)

**Feature:** 03-shared-infrastructure
**Plan:** [PLAN.md](./PLAN.md) · **Tasks:** [TASKS.md](./TASKS.md)

---

## Status

**COMPLETE — 13/13 tracked tasks verified.** Started and finished 2026-08-09, in a single continuous session, immediately after DW-19/DW-20 closure, on explicit instruction.

## Progress

13 / 13 tracked tasks complete.

| Area | Complete | State |
|---|---|---|
| A — Real-Time Publisher | 3/3 | ✅ Verified |
| B — File Storage Port + MinIO Adapter | 6/6 | ✅ Verified |
| C — Documentation | 2/2 | ✅ Verified |
| D — Verification & Close-Out | 2/2 | ✅ Verified |

## What Was Built

### Area A — Real-Time Publisher

`RedisRealtimePublisher` implements the existing `RealtimePublisher` port (`application/common/ports.py`) over the existing `RedisClient` connection pool — no new dependency, no new infrastructure service, exactly the "arrives with the phase that needs it" gap `RedisClient`'s own docstring anticipated. Wired into `AppState` alongside the other process-wide resources.

Deliberately excludes the WebSocket connection manager and per-subscription RBAC authorization (`16-realtime-architecture.md` §3, §5) — that needs real Authentication (Phase 6) to authorize a subscription the way a REST `GET` is authorized today. Building it now would mean either no authorization or authorization against the interim, explicitly-untrusted `HeaderTenantResolver`, the same reasoning that kept DW-12 open through Phase 2.

### Area B — File Storage Port + MinIO Adapter

`FileStorage` protocol (`upload`/`download`/`delete`/`exists`/presigned `url`) added to `application/common/ports.py`, tenant-scoped key convention (`tenant/{id}/...`). Concrete adapter `S3CompatibleFileStorage` (`infrastructure/storage/client.py`) over `aioboto3`, held for the process lifetime like every other infrastructure client in this codebase, idempotent bucket creation on connect. MinIO added to `infrastructure/docker/docker-compose.yml` — the local-dev object store `docs/architecture/13-deployment.md` had already anticipated but never built.

**Deliberately no production adapter.** Azure Blob Storage (the illustrative deployment target) isn't S3-compatible, and hosting topology remains an open decision (ADR-022). Recorded as ADR-030 and a new Deferred Decisions entry, not a silent gap — `.env.prod.example`'s storage section is empty with a comment explaining exactly why.

### Area C — Documentation

New **ADR-030** records the port shape and the MinIO-now/cloud-adapter-later split. Updated `13-deployment.md`, `knowledge/02-tech-stack.md`, `knowledge/12-current-status.md`, `planning/current_phase.md`.

## Verification (2026-08-09)

| Check | Result |
|---|---|
| `ruff check` | ✅ All checks passed |
| `ruff format --check` | ✅ (2 files auto-formatted during the phase, re-verified clean) |
| `mypy --strict` | ✅ 0 issues, 87 source files |
| `import-linter` | ✅ 5/5 contracts kept, 86 files, 212 dependencies |
| `pytest -q` (full suite) | ✅ **192/192 passed** (was 184 before this phase's own 8 new tests; 0 regressions against Phase 1/2) |

New integration tests, both against real backing services (never mocked, per `docs/implementation/testing-strategy.md`):
- `tests/integration/test_realtime_publisher.py` — 2 tests. A real Redis subscriber receives the published, JSON-decoded message; publishing to a channel with no subscriber doesn't raise.
- `tests/integration/test_file_storage.py` — 8 tests. Upload→download round-trip, download of a missing key returns `None`, delete removes/is idempotent on a missing key, `exists` true/false, **a presigned URL is genuinely fetched over real HTTP** (not just generated and trusted), `ping`.

## Still Open (not this phase's scope, not blockers)

- WebSocket connection manager + subscription authorization (`16-realtime-architecture.md` §3, §5) — needs Phase 6 Authentication.
- Production object-storage vendor — deferred with hosting topology (ADR-022, ADR-030's Deferred Decisions entry).
- Every business use case that will eventually call these two ports (KYC upload, delivery photo capture, order/delivery status push, invoice storage) — arrives with the modules that own them, unchanged from this phase's explicit exclusions in `PLAN.md`.

## Last Updated

2026-08-09 — phase complete, all areas verified.
