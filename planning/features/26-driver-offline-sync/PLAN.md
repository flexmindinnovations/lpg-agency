# Plan: Driver App Offline-First Sync

**Phase:** 26
**Status:** Stage 1 done 2026-09-02 (`uv run pytest` 1130 pass, ruff / mypy src / lint-imports clean) · Stages 2–7 pending
**Requirement:** ADR-008 / D-24 — mandatory offline-first for the Driver App,
deferred since Phase 5 (`local_storage` shipped the encrypted DB + one
foundation table only; the sync queue + conflict resolution were explicitly
scoped to "once the Driver App has real offline features to drive them").

---

## Context

The driver app is **not** offline-first today, despite it being a hard,
accepted requirement. What already exists:

- [`DriftLocalDatabase`](../../../mobile/packages/local_storage/lib/src/drift_local_database.dart)
  (SQLCipher-encrypted, key in Keychain/Keystore) opens before the first
  frame in [`main.dart`](../../../mobile/apps/driver_app/lib/main.dart);
  `AppDatabase` (schema v3) carries `SyncOperations` + `CachedResources`
  tables.
- A [`SyncCoordinator`](../../../mobile/packages/sync_engine/lib/src/sync_coordinator.dart)
  is instantiated and `.start()`-ed (10-second poll loop) in `main.dart` —
  **but** `syncCoordinatorProvider` is never overridden, `enqueueOperation`
  is never called anywhere in the driver app, and `_dispatch` only knows the
  Customer App's `order_gas` op plus a dead `delivery_confirmation` case that
  posts to `/deliveries/sync` (not a real backend route).
- [`ResourceCache`](../../../mobile/packages/local_storage/lib/src/resource_cache.dart)
  — a cache-first read helper over `CachedResources` — exists and is **used
  by nothing**.
- Every driver mutation (`departOrder`, `deliverOrder`,
  `recordFailedDelivery`, `declare` cash handover) is a live Dio call that
  fails hard, with no queue and no retry, the moment signal drops mid-route.
- No `connectivity_plus` anywhere in the workspace — the coordinator's own
  comment notes it "should also trigger on connectivity restoration events".

**Backend readiness:**

| Endpoint | Idempotency-Key today |
|---|---|
| `POST /api/v1/orders` | ✅ required ([`IdempotencyService`](../../../backend/src/lpg/infrastructure/idempotency/service.py)) |
| `POST /api/v1/orders/{id}/deliver` | ✅ required |
| `POST /api/v1/orders/{id}/depart` | ❌ none |
| `POST /api/v1/orders/{id}/failed-delivery` | ❌ none |
| `POST /api/v1/orders/{id}/reschedule` | ❌ none |
| `POST /api/v1/cash-handovers` | ❌ none |

`IdempotencyService` is Redis-backed: first request claims the key and runs
the operation, a repeat with the same request fingerprint replays the stored
result, a repeat with a *different* fingerprint raises
`IdempotencyConflictError` (409). Result replay TTL is **24 h**.

---

## Goal

A driver in a signal dead zone can:

1. open the app and see their assigned route + stops from cache;
2. record depart / delivery / failed-delivery / cash-handover offline, with
   the UI updating optimistically;
3. have every one of those sync automatically and **idempotently** when
   signal returns — a retried sync never double-applies;
4. see a clear, actionable list of anything that failed or conflicted, with
   the server always authoritative.

---

## Decisions (baked into this plan)

1. **`Idempotency-Key` is optional** on the four retrofitted endpoints — used
   when the header is present, else the endpoint generates a per-request
   UUID. The web dashboard already calls `departOrder` / `rescheduleOrder`
   ([`order-detail.ts:299`](../../../frontend/libs/order/feature-orders/src/lib/order-detail/order-detail.ts))
   and stays untouched; the driver app (the only offline client) always
   sends one. `deliver` / `create` keep their **required** contract.
2. **Client-side offline validation** ("empties collected ≤ cylinders loaded
   on the van", per `05-mobile-architecture.md` §2) is **out of scope** — it
   depends on a van-load inventory snapshot that does not exist yet (coupled
   to the separate van-load-confirmation gap). Tracked as a follow-up.
3. **Conflict UX** is "acknowledge & discard", not a field-by-field merge
   screen — the server is authoritative (§3), so a rejected mutation is
   shown with its reason and the driver clears it.
4. **Idempotency result TTL** goes 24 h → 72 h so a phone offline over a long
   weekend still gets replay protection. Beyond 72 h the DB-level guards
   (`uq_cash_handover_route`, the `out_for_delivery → delivered` transition
   guard) are the backstop.

---

## Stage 1 — Backend: idempotency on the remaining driver mutations

Thread `IdempotencyService.execute` + `fingerprint(...)` (the exact
`deliver_order` pattern — `request: Request` param, read the header, wrap the
use-case call in an `async def _operation()` returning `.model_dump(mode="json")`)
through:

- `POST /orders/{id}/depart` (`depart_order`, [`order.py:747`](../../../backend/src/lpg/api/v1/routers/order.py))
- `POST /orders/{id}/failed-delivery` (`record_failed_delivery`, ~`order.py:929`)
- `POST /orders/{id}/reschedule` (`reschedule_order`, ~`order.py:786`)
- `POST /cash-handovers` (`declare`, [`cash_handover.py`](../../../backend/src/lpg/api/v1/routers/cash_handover.py))

Differences from `deliver_order`:

- The header is **optional**: `idempotency_key = request.headers.get("Idempotency-Key") or str(uuid.uuid4())` — no `HTTPException` when absent.
- Bump `_RESULT_TTL_SECONDS` (24 h → 72 h) in
  `idempotency/service.py`.

**Tests** (`backend/tests/integration/`):

- Each endpoint: first call applies the transition; same key + same body
  replays the stored response body verbatim without re-running; same key +
  different body → 409 `IDEMPOTENCY_KEY_CONFLICT`; no header → still works
  (fresh key each call).
- `cash-handovers`: replay returns the same `CashHandoverResponse`; a second
  *distinct* key on an already-reconciled route still hits the existing
  `uq_cash_handover_route` 409.

**Gate:** `uv run pytest`, `uv run ruff check src tests`, `uv run mypy src`,
`uv run lint-imports`.

**Commit:** `feat(backend): idempotency-key on depart/failed-delivery/reschedule/cash-handover`

### ✅ DONE 2026-09-02

- `idempotency/service.py` — `import uuid` moved to runtime; `_RESULT_TTL_SECONDS`
  24 h → **72 h**; new `run_idempotent(service, *, tenant_id, idempotency_key,
  fingerprint_payload, operation)` helper that mints a random key when the
  caller passes `None` (the optional-key contract). `deliver` / `create` keep
  their own inline "header required" check, untouched.
- `routers/order.py` — `depart_order`, `reschedule_order`,
  `record_failed_delivery` each gained `request: Request` +
  `idempotency_service` params and wrap the use-case call in an
  `async def _operation()` passed to `run_idempotent`. Fingerprint payload:
  `{"order_id": ...}` for depart/reschedule (no body),
  `{"order_id": ..., **body.model_dump(mode="json")}` for failed-delivery.
- `routers/cash_handover.py` — `declare_cash_handover` gained
  `http_request: Request` (the body param is already named `request`) +
  `idempotency_service`; imports `get_idempotency_service` from
  `dependencies.order`. `declared_by` hoisted to a local before the closure
  so mypy keeps the `None`-narrowing.
- Tests: `test_order_endpoints_smoke.py` — depart replay asserts **no second
  OTP** is issued; failed-delivery replay + a same-key-different-body → 409;
  reschedule replay. `test_cash_handover_endpoints_smoke.py` —
  `test_declaration_replays_under_the_same_idempotency_key` (replay returns
  the same `id`, `COUNT(*) == 1`). The pre-existing
  `test_second_declaration_for_a_route_is_a_conflict` still passes (no key →
  fresh minted key each call → real `uq_cash_handover_route` 409).
- Gate: `uv run pytest` **1130 passed**; ruff / mypy src / lint-imports (5/5)
  clean.
- **No web-dashboard change** — the key is optional, so `order-detail.ts`'s
  `departOrder` / `rescheduleOrder` calls are unaffected.

---

## Stage 2 — `sync_engine`: a real driver mutation queue

`packages/sync_engine/lib/src/sync_coordinator.dart`:

- **Rewrite `_dispatch`** — drop `delivery_confirmation`; keep `order_gas`;
  add structured driver ops. Payload is JSON `{"path": "...", "body": {...}}`;
  every op sends `Idempotency-Key: op.idempotencyKey`:

  | `op.type` | method + path |
  |---|---|
  | `order_depart` | `POST /api/v1/orders/{id}/depart` |
  | `order_deliver` | `POST /api/v1/orders/{id}/deliver` (media handled in Stage 5) |
  | `order_failed_delivery` | `POST /api/v1/orders/{id}/failed-delivery` |
  | `order_reschedule` | `POST /api/v1/orders/{id}/reschedule` |
  | `cash_handover_declare` | `POST /api/v1/cash-handovers` |

- **409 handling** (`_processOperation`): inspect the problem-details
  `error_code`. `IDEMPOTENCY_KEY_CONFLICT` → log and mark `synced` (our own
  bug, nothing to retry). Any other 409 (a genuinely stale transition —
  another device or the office already moved the aggregate) → `status =
  'conflict'` with the server message.
- **Retry policy** — add a `retryCount` int column (schema **v4** migration:
  `if (from < 4) await m.addColumn(syncOperations, syncOperations.retryCount)`).
  Capped exponential backoff (skip an op whose `lastAttemptAt + backoff(retryCount)`
  is in the future); after `_maxRetries` (e.g. 8) → `status = 'failed'`,
  stop retrying, surface it.
- **Connectivity** — add `connectivity_plus` to `sync_engine`. On a
  transition to online, call `syncNow()`. Keep the periodic `Timer` as the
  fallback (raise it to 30 s since connectivity now drives the common case).
- **Providers** (`sync_engine.dart` barrel):
  - `syncCoordinatorProvider` (overridden in `main.dart`).
  - `pendingSyncCountProvider` — `Stream<int>` over
    `SyncOperations where status in (pending, error, syncing)`.
  - `syncIssuesProvider` — `Stream<List<SyncOperation>>` where
    `status in (failed, conflict)`.
  - `connectivityProvider` — `Stream<bool>` online/offline.

**Tests** (`packages/sync_engine/test/`):

- Each op type dispatches to the right method/path and sends the op's
  idempotency key as the header.
- 409 `IDEMPOTENCY_KEY_CONFLICT` → `synced`; 409 other → `conflict`.
- Retry cap: an op erroring `_maxRetries` times ends `failed`.
- A connectivity `false → true` event triggers `syncNow`.
- Migration v3 → v4 adds `retry_count` with existing rows defaulted to 0.

**Commit:** `feat(mobile): real offline mutation queue in sync_engine (driver ops + retry + connectivity)`

---

## Stage 3 — Driver app: cache-first reads

`mobile/apps/driver_app/lib/src/`:

- `local_database_provider.dart` — add `resourceCacheProvider` returning
  `ResourceCache(ref.watch(localDatabaseProvider).database)`.
- Rework the three read providers to **cache-first, refresh, fall back to
  cache on network error** (write-through on every successful fetch):
  - [`active_route_provider.dart`](../../../mobile/apps/driver_app/lib/src/features/delivery/data/active_route_provider.dart)
    — `activeRouteProvider` caches `('route_active', driverId)`. **Verify
    whether `RouteSummary` carries stops**; if not, add a `routeStopsProvider`
    (`GET /routes/{id}/stops` or whatever the stop-list source is) and cache
    `('route_stops', routeId)` — the driver must be able to work the stop
    list entirely from cache.
  - [`stop_order_provider.dart`](../../../mobile/apps/driver_app/lib/src/features/delivery/data/stop_order_provider.dart)
    — `stopOrderProvider(orderId)` caches `('order', orderId)`.
  - `routeHistoryProvider` caches `('route_history', driverId)` (list).
- A reusable `OfflineBanner` (design-system styled) driven by
  `connectivityProvider` — shown on Today, Deliveries, Stop Detail:
  "Offline — showing last synced data".

**Tests:**

- Each provider: API success writes the cache; API throws → returns the
  cached value; no cache + API throws → error state.
- `OfflineBanner` renders only when `connectivityProvider` is `false`.

**Commit:** `feat(mobile): cache-first reads + offline banner in the driver app`

---

## Stage 4 — Driver app: non-media writes through the queue

- New `delivery_mutations_repository.dart` — `departStop`,
  `recordFailedDelivery`, `declareCashHandover`. Each:
  1. generates a client op UUID (`const Uuid().v4()`);
  2. writes optimistic local state — overwrite the cached `('order', id)`
     row (or `('route_cash', routeId)`) with the post-transition status;
  3. `ref.read(syncCoordinatorProvider).enqueueOperation(type, jsonEncode({path, body}))`;
  4. returns optimistic success immediately.
- Order/stop providers **overlay pending-op state**: if a `SyncOperation`
  is pending/errored for this order id, surface a "Pending sync" chip
  ([`LpgStatusBadge`](../../../mobile/packages/design_system) severity
  `info`) on the stop tile and stop detail.
- Wire the screens:
  - [`stop_detail_screen.dart`](../../../mobile/apps/driver_app/lib/src/features/delivery/presentation/stop_detail_screen.dart)
    `_actions` — "Start this delivery" and the failed-delivery sheet call the
    repository, then `context.go('/')` + invalidate.
  - [`cash_handover_screen.dart`](../../../mobile/apps/driver_app/lib/src/features/cash_handover/presentation/cash_handover_screen.dart)
    — "Declare handover" calls the repository.
- Keep the online path fast: `enqueueOperation` already calls `syncNow()`
  synchronously, so an online driver still round-trips in ~one tick.

**Tests:**

- Offline `departStop` → op row `pending`, cached order shows
  `out_for_delivery`, screen navigates home.
- Pending op → "Pending sync" chip on the stop.
- Cash-handover declare offline → queued + optimistic receipt state.

**Commit:** `feat(mobile): queue depart / failed-delivery / cash-handover offline`

---

## Stage 5 — Offline delivery + media queue

The hard one: `deliver` carries a signature PNG + a photo JPEG, currently
uploaded inline via `POST /orders/{id}/pod-attachments` (multipart) before
the JSON `deliver` call.

- **Local media store** — write the bytes to
  `<app-support>/pod_media/<opId>_signature.png` /
  `<opId>_photo.jpg`; the `order_deliver` payload references those paths plus
  a `mediaRefs` slot (initially empty).
- **Multi-step `_dispatch` for `order_deliver`:**
  1. for each local media file without a stored `blob_ref`: `POST
     .../pod-attachments` (multipart), capture `blob_ref`, **persist it back
     onto the op row** (so a crash mid-sequence doesn't re-upload);
  2. `POST .../deliver` with the collected refs + GPS + payment + OTP + the
     op's `Idempotency-Key`;
  3. on success, delete the local media files.
- [`record_delivery_screen.dart`](../../../mobile/apps/driver_app/lib/src/features/delivery/presentation/record_delivery_screen.dart)
  `_submit` — when offline, persist media locally + enqueue `order_deliver`
  + optimistic `delivered` + `context.go('/')`; when online, the existing
  inline path (which the queue also uses under the hood — unify on the
  repository).
- Compress the photo client-side before persisting (arch doc §9) — already
  `imageQuality: 60` on capture; keep.

**Tests:**

- Offline deliver → media files on disk, op `pending` with `mediaRefs: []`.
- `_dispatch` uploads media, stores refs, then calls `/deliver` with them;
  a simulated failure after upload-1 → retry resumes from upload-2.
- Successful sync deletes the local media.

**Emulator:** airplane mode → full POD capture → "Delivery recorded"
(optimistic) → re-enable Wi-Fi → within ~30 s the op drains, POD attachments
land in blob storage, `notification_log` shows the `delivery_confirmed`
push, Today shows the real advanced count.

**Commit:** `feat(mobile): offline proof-of-delivery with a media upload queue`

---

## Stage 6 — Conflict & failure surfacing

- New `SyncStatusScreen` (route `/sync`, reached from a Profile-tab row
  "Sync status — N pending" / "N need attention"):
  - **Pending** — count + "Sync now" button (`syncNow()`).
  - **Failed** (`status = 'failed'`) — op summary + reason + "Retry"
    (resets `retryCount`, `status = 'pending'`).
  - **Conflicts** (`status = 'conflict'`) — op summary + server message +
    "Acknowledge & discard" (`status = 'synced'`, drop optimistic local
    state, invalidate the affected providers so the screen reloads server
    truth).
- Optional: a small count badge on the Profile tab icon (reuse the Alerts
  badge pattern from Phase 25).

**Tests:**

- `syncIssuesProvider` drives the list; retry resets the row; acknowledge
  clears it.
- Widget: failed + conflict rows render with the right actions.

**Emulator:** deliver a stop the office cancelled while the driver was
offline → op → `conflict` → appears in Sync status → acknowledge → stop
detail reloads to the cancelled state.

**Commit:** `feat(mobile): driver sync-status screen (pending / failed / conflicts)`

---

## Stage 7 — E2E + docs

- `integration_test/offline_sync_test.dart` — the full offline round-trip
  (arch doc §9 calls this out specifically): cache a route online → go
  offline → depart + deliver a stop → come online → assert the queue drains
  and server state matches.
- `planning/features/26-driver-offline-sync/STATUS.md` (new) + update
  `planning/features/24-driver-app-shell/STATUS.md` ("offline-first: done").
- Memory: new `reference_driver_offline_sync.md`; note in
  `project_lpg_agency_status.md` that the ADR-008 sync-queue item is closed.

**Commit:** `test(mobile): offline-sync integration test + docs`

---

## Risks / notes

- **Web dashboard callers** of `depart` / `reschedule` — safe because the
  key is optional (Decision 1). If a future change makes it required, the
  two call sites in `order-detail.ts` + a regen of the generated client are
  the work.
- **Optimistic-state divergence** — the cached order row and the pending-op
  overlay must have one clear precedence rule (pending op wins until it
  reaches `synced`/`conflict`). Centralise in the order provider, not per
  screen.
- **Idempotency > 72 h offline** — replay protection lapses; DB guards
  (`uq_cash_handover_route`, transition guards) are the backstop. Acceptable.
- **Media disk growth** — files must be deleted on successful sync *and*
  swept on app start for any op already `synced`.
- **Op ordering** — the coordinator already processes `orderBy(createdAt
  asc)` globally, which preserves per-aggregate order. Keep that.
- **Route data the driver never fetched online** — cache only holds what was
  loaded; a driver who never opened the route on Wi-Fi at the depot sees
  nothing offline. Acceptable per the field workflow.
- **`connectivity_plus` reports reachability, not captive portals** — the
  retry/backoff loop is still the real safety net; connectivity is just an
  optimisation.

## Follow-ups (explicitly not in this plan)

- Client-side offline validation (empties ≤ loaded) — needs van-load data.
- Van-load confirmation screen (`inventory:load`) — separate gap.
- Extracting `PushNotificationService` into `packages/push` (Phase 25 debt).

---

## References

- `docs/architecture/05-mobile-architecture.md` §3 (offline-first strategy),
  §7 (encrypted local storage), §9 (idempotency contract, integration tests)
- `docs/architecture/15-architecture-decision-records.md` ADR-008, ADR-034
- Phase 24 [`STATUS.md`](../24-driver-app-shell/STATUS.md) — the delivery
  workflow this sits under
