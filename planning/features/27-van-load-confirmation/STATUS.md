# Status: Van-Load Confirmation

**Phase:** 27
**Status:** Stages 1–6 done 2026-09-03 — the non-mandatory Driver-App
van-load gap (flagged since Phase 26) is closed; the client-side
"empties ≤ loaded" check `05-mobile-architecture.md` §2 asked for is in.

## Context

The office loads the van (`POST /routes/{id}/load`, `routes:manage`) and the
route moves `planned → loaded`, but the driver had no screen — they got the
Phase 25 `route_ready` push and nothing else. No visibility of what's on the
van, no accountability step, and the Driver App had no loaded quantities for
the offline empties check. Plan: [PLAN.md](./PLAN.md).

Design: a **soft** confirmation — the driver views the manifest and
acknowledges it (timestamp + `RouteLoadConfirmed` event). Not a depart gate.
Mirrors cash-handover: read screen + confirm action + Today nudge, no
route-lifecycle change.

## What shipped

| Stage | Commit | Summary |
|---|---|---|
| — planning | `db1a3af` | PLAN.md |
| 1 — Backend | `24788b4` (+ `d4c2ded` pubspec precursor) | `delivery.route` gains `loaded_lines` (JSONB, snapshotted at `→ loaded`) + `load_confirmed_at`; `Route.record_load_manifest` / `confirm_load` (idempotent, `InvariantViolation` if not `loaded`); `RouteLoadConfirmed` event; `ConfirmRouteLoadUseCase`; `POST /routes/{id}/confirm-load` (`routes:deliver`, optional `Idempotency-Key`, driver-ownership → 404); `RouteResponse` + `GET /routes/active` carry both fields. Migration `b3e1d7a24f90`. |
| 2 — api_client | `972c5c5` | `RouteLoadLine` model; `RouteSummary.loadedLines` / `loadConfirmedAt` / `isLoadPending`; `RouteApi.confirmLoad(routeId, {idempotencyKey})`. |
| 3 — Driver app | `7257940` | `features/van_load/` — `routeLoadProvider` (names resolved cache-first via `getList` on `/admin/cylinder-types`), `VanLoadScreen` (manifest card + "Confirm load"), `pendingLoadProvider` + Today `_PendingLoadCard` nudge; `DeliveryMutations.confirmLoad` (optimistic cache stamp + queued `route_confirm_load`); `SyncCoordinator` dispatches it; `vanLoad` route nested under the Deliveries branch. |
| 4 — Empties check | `26f843f` | `queuedEmptiesByTypeProvider` sums queued `order_deliver` empties by type; `record_delivery_screen` `_QuantityRow` shows an amber **soft warning** when `queued elsewhere + this stop > loaded` for a type. Never blocks; the per-stop caps (`empties ≤ delivered ≤ ordered`) still hold. |
| 5 — Office notification | `a07b2c5` | `RouteLoadConfirmed` → `route_load_confirmed_staff` in-app notification (tenant-wide `_STAFF_ALERT_ROLES`, no email/SMS/push), reusing the `cash_shortfall_staff` recipient + reference branches. |
| 6 — Verify + docs | _this_ | Live API round trip; APK build/install/launch smoke; these docs; memory. |

## Verification

- **Gate:** `backend` `uv run pytest` **1143 pass** (ruff / mypy src 293 files /
  lint-imports 5/5 clean). Mobile: `sync_engine` **15**, `api_client` **55**,
  `driver_app` **77** — all `flutter analyze` clean.
- **Live API round trip** (dev backend + arq, `scratchpad/stage6_roundtrip.py`,
  route mutated to `loaded` then restored): `GET /routes/{id}` returns the
  2-line manifest with `load_confirmed_at: null` → `POST /confirm-load` with an
  `Idempotency-Key` → `200`, timestamp stamped → replay with the same key →
  same timestamp (idempotent) → a third confirm with no key → `200` no-op
  (domain guard). arq then delivered **3** `route_load_confirmed_staff` in-app
  notifications — to `manager`, `dispatcher`, `agency_admin` — titled "Van
  Load Confirmed", body "The driver confirmed the van load for route
  #0A50A77F."
- **Emulator** (`emulator-5554`, debug APK `--dart-define-from-file` vs.
  `10.0.2.2:8000`): `flutter build apk --debug` clean; installs; cold-launch
  reaches the Flutter engine + Dart VM with no `FATAL` / Dart exception,
  `MainActivity` focused. A full logged-in manifest→confirm walkthrough
  wasn't run here — the seeded `e2e.driver` has only `in_progress` routes so
  `/routes/active` returns no `loaded` route without more data surgery; that
  path is covered by `van_load_screen_test`, the `today_screen_test` nudge
  case, and `record_delivery_screen_test`'s warning cases.

## Deviations from the plan

- **"not loaded" → 409 `INVARIANT_VIOLATION`**, not the plan's 422 — the
  codebase maps every `DomainError` to 409.
- **`loaded_lines` carries `{cylinder_type_id, quantity}` only** — no
  `cylinder_type_name`. The Driver App resolves names client-side from a
  cache-first `/admin/cylinder-types` read (that endpoint has no permission
  gate), which also keeps the manifest legible offline.
- **Empties running tally counts queued deliveries only** — a synced delivery
  has already cleared the server and its order is gone from local data. Can
  under-count early in a route; fine for a soft check.
- **Stage 5 skips email** (unlike `cash_shortfall_staff`) — a load
  confirmation is informational, not a money trail. In-app only.

## Follow-ups (not in scope)

- **Hard depart gate** — if the office ever wants `depart` to require a
  confirmed load, it's a one-line guard in `DepartOrderUseCase`
  (`loaded → in_progress`) on top of this.
- **Route re-load / top-up** — `loaded_lines` would need to be additive and
  `load_confirmed_at` reset. `load` only accepts `planned` today, so N/A.
- **iOS** — driver app still Android-only.

## Notes

- Plan: [PLAN.md](./PLAN.md)
- Sits under the Phase 24 delivery workflow —
  [24-driver-app-shell/STATUS.md](../24-driver-app-shell/STATUS.md); builds on
  the Phase 26 queue/cache-first infra —
  [26-driver-offline-sync/STATUS.md](../26-driver-offline-sync/STATUS.md).

## Last Updated

2026-09-03 — Stage 6: live API round trip + emulator smoke + docs.
