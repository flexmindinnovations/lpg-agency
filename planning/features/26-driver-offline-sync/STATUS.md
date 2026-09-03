# Status: Driver App Offline-First Sync

**Phase:** 26
**Status:** Stages 1–7 done 2026-09-03 — the mandatory ADR-008 / D-24
offline-first requirement for the Driver App is satisfied.

## Context

The Driver App shipped (Phases 5/6/12/19/24/25) without the offline-first
behaviour D-24 makes mandatory: `DriftLocalDatabase` (encrypted) and a
`SyncCoordinator` skeleton existed from Phase 5 but nothing used them — every
driver mutation was a live HTTP call that failed hard in a signal dead zone,
and reads errored offline. Plan: [PLAN.md](./PLAN.md).

## What shipped

| Stage | Commit | Summary |
|---|---|---|
| 1 — Backend idempotency | `55099eb` | `Idempotency-Key` (optional) on `depart` / `failed-delivery` / `reschedule` / `cash-handovers`; replay TTL 24h → 72h. |
| 2 — Real mutation queue | `2a864ff` | `SyncCoordinator` rewrite: structured driver ops in `_dispatch`, 409 branching (`IDEMPOTENCY_KEY_CONFLICT`→failed, other→conflict), retry + capped backoff (schema v4: `retryCount`/`lastAttemptAt`), `connectivity_plus` drain trigger. |
| 3 — Cache-first reads | `fb71262` | `CacheFirstReader` (write-through, fall back to cache, evict on 404); `activeRouteProvider` / `routeHistoryProvider` / `stopOrderProvider` reworked; `OfflineBanner` + `connectivityProvider`; sync-queue providers wired; logout clears the cache. |
| 4 — Non-media writes | `3860416` | `DeliveryMutations` — `departStop` / `recordFailedDelivery` / `declareCashHandover` optimistic + queued; `pendingSyncAggregatesProvider` overlay (reads go cache-only while an op is queued); "PENDING SYNC" chips. |
| 5 — Offline POD + media | `8839d54` | `MediaStore` / `FileMediaStore`; `_dispatchDeliver` — resumable upload×N then deliver, same key, cleanup on success; `recordDelivery` online-inline (immediate OTP errors) / offline-queued. |
| 6 — Conflict surfacing | `c045fcc` | `SyncStatusScreen` (`/sync`) — pending + "Sync now", failed + Retry, conflict + "Acknowledge & discard"; Profile row + tab badge dot. |
| 7 — E2E + docs | _this_ | Offline round-trip test; `dart_test.yaml` concurrency cap; emulator smoke; these docs; memory. |

## Verification

- **Gate:** `backend` `uv run pytest` 1130 pass (ruff / mypy src / lint-imports
  clean). Mobile: `sync_engine` 14, `local_storage` 14, `driver_app` 70,
  `customer_app` 45, `api_client` 53 — all `flutter analyze` clean.
- **Round trip** (`test/offline/round_trip_test.dart`): cache a stop's order
  → go offline → `departStop` + `recordDelivery` (media held locally, ops
  queued, optimistic `delivered`) → back online → `syncNow` drains
  `depart` → `pod-attachments` ×2 → `deliver` in order, both ops `synced`,
  media cleaned up.
- **`dart_test.yaml`** caps `driver_app` test concurrency to 2 — the
  in-memory-SQLite offline suites and the pre-existing geolocator
  `location_sharing` suite flake at full parallelism; serial and capped runs
  are 70/70 green.
- **Emulator** (`emulator-5554`, debug APK vs. `10.0.2.2:8000`): builds and
  cold-starts clean; Today shows the live route via the cache-first path;
  Profile → "Sync status" → `SyncStatusScreen` ("Everything's synced");
  airplane mode → the offline banner appears and the cached route still
  renders. Cosmetic fix from this pass: shell body wrapped in `SafeArea`.

## Follow-ups (not in scope)

- **Client-side offline validation** (`empties collected ≤ cylinders loaded`,
  `05-mobile-architecture.md` §2) — needs a van-load inventory snapshot that
  doesn't exist yet. Coupled to the separate van-load-confirmation gap.
- **iOS** — the driver app is still Android-only (blocked on a paid Apple
  Developer account, same as customer_app).
- `PushNotificationService` dedupe into `packages/push` (Phase 25 debt).

## Notes

- Plan: [PLAN.md](./PLAN.md)
- Sits under the Phase 24 delivery workflow — [24-driver-app-shell/STATUS.md](../24-driver-app-shell/STATUS.md).

## Last Updated

2026-09-03 — Stage 7: round-trip test + concurrency cap + docs.
