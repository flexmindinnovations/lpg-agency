# TASKS — Phase 3: Shared Infrastructure (Real-Time Publisher, File Storage)

Legend: `[ ]` not started · `[~]` in progress · `[x]` complete and verified (build+lint+types+tests all re-run, not inspected)

---

## A — Real-Time Publisher ✅ Complete 2026-08-09

- [x] **T-01** `RedisRealtimePublisher` (`infrastructure/realtime/publisher.py`) implementing the existing `RealtimePublisher` port over `RedisClient`. JSON-serializes the message dict, `PUBLISH`es to the given channel.
  *Verify:* `ruff check`, `mypy --strict`, `import-linter` (added `lpg.api.app -> lpg.infrastructure.realtime.publisher` to the composition-root exception list) all clean.
- [x] **T-02** Wired into `AppState`/lifespan (`api/app.py`) as `_state.realtime_publisher`, constructed from the same `RedisClient` instance, torn down alongside it. No new health check needed — reuses `RedisHealthCheck`.
- [x] **T-03** Round-trip proof test (`tests/integration/test_realtime_publisher.py`, 2 tests): a real Redis subscriber on the channel receives the JSON-decoded message published by `RedisRealtimePublisher`; publishing to a channel with no subscriber does not raise (Pub/Sub's fire-and-forget semantics, ADR-015).
  *Verify:* `pytest tests/integration/test_realtime_publisher.py` — 2/2 passed against real Docker Redis. Full suite re-run: 184/184 passed, zero regression.

## B — File Storage Port + MinIO Adapter ✅ Complete 2026-08-09

- [x] **T-04** `FileStorage` protocol (`application/common/ports.py`) — `upload`, `download`, `delete`, `exists`, presigned `url`. Tenant-scoped key convention, mirroring `CacheClient`'s `tenant:{id}:...` (here: `tenant/{id}/...`, since S3 keys are path-shaped).
- [x] **T-05** MinIO added to `infrastructure/docker/docker-compose.yml` (ports 59000/59001, `mc ready local` healthcheck), `aioboto3` + `types-aiobotocore[s3]` (dev, for `mypy --strict`) added to `backend/pyproject.toml`.
- [x] **T-06** `S3CompatibleFileStorage` (`infrastructure/storage/client.py`) — `aioboto3`-backed adapter, connection held for the process lifetime (matching `Database`/`RedisClient`/`JobQueue`'s lifecycle, not a fresh `async with` per call). Idempotent bucket creation on connect (`head_bucket` → `create_bucket` on miss).
- [x] **T-07** `StorageHealthCheck` (`infrastructure/health.py`), wired into `AppState`/lifespan/readiness. `storage.connect()` degrades to not-ready on failure rather than crashing startup, mirroring `JobQueue`'s existing pattern.
- [x] **T-08** `LPG_STORAGE_*` settings (endpoint, access key, secret key, bucket, region) added to `Settings`, discrete + defaulted to the local MinIO container. `.env.dev.example`/`.env.uat.example` populated (separate buckets, same instance — mirrors the Redis logical-DB / Postgres separate-database pattern); `.env.prod.example` left deliberately empty with a comment explaining why (production vendor undecided, ADR-030).
- [x] **T-09** `tests/integration/test_file_storage.py` — 8 tests against real MinIO: download-missing → None, upload→download round-trip, delete removes/is idempotent, exists true/false, **presigned URL is genuinely fetchable over real HTTP** (not just generated), ping.
  *Verify:* `pytest tests/integration/test_file_storage.py` — 8/8 passed. Full suite re-run: 192/192 passed, zero regression.

## C — Documentation ✅ Complete 2026-08-09

- [x] **T-10** ADR-030 (`docs/architecture/15-architecture-decision-records.md`) records the file-storage port shape, why MinIO now and not Azure Blob (not S3-compatible, hosting topology still open per ADR-022), and the deferred-decision entry for the production vendor.
- [x] **T-11** Updated `docs/architecture/13-deployment.md` (implementation note under the capability table), `knowledge/02-tech-stack.md` (Object Storage row), `knowledge/12-current-status.md` (Shared Infrastructure priority marked complete), `planning/current_phase.md`.

## D — Verification & Close-Out ✅ Complete 2026-08-09

- [x] **T-12** Full backend verification: `ruff check` clean, `ruff format --check` clean (2 files auto-formatted), `mypy --strict` clean (87 source files), `import-linter` 5/5 contracts kept (86 files, 212 dependencies).
- [x] **T-13** `pytest -q` — **192/192 passed**, zero regression against Phase 1/2. This `STATUS.md` updated.
