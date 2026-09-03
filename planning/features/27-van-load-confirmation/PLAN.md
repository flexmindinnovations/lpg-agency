# Plan: Van-Load Confirmation

**Phase:** 27
**Status:** Stages 1–4 done 2026-09-03 · Stages 5–6 pending
**Type:** Non-mandatory Driver-App gap (flagged since Phase 26). Also unblocks
the client-side "empties ≤ loaded" validation (`05-mobile-architecture.md` §2).

---

## Context

- The office loads the van via **`POST /routes/{id}/load`** (`routes:manage`,
  BR-12) — `LoadVehicleForRouteUseCase` does an atomic warehouse → vehicle
  transfer and moves the route `planned → loaded`.
- The driver holds `inventory:load` but has **no screen**. When the route
  hits `loaded` they get the Phase 25 `route_ready` push and nothing else —
  they can't see what's supposed to be on the van, and there's no
  accountability step before they start delivering.
- `GET /inventory-locations/vehicle/{id}/balance` exists but needs
  `inventory:read` (the driver has only `inventory:load`), and it returns the
  *current* balance, not the load manifest.
- `RouteResponse` today: `id, tenant_id, branch_id, driver_id, vehicle_id,
  date, status, version, stops`. No load info.
- Driver-scoped route reads use `_resolve_read_scope` (`driver` → own id).
  The active route is `GET /routes/active` (`routes:read`).

## Design decision — soft confirmation, no new lifecycle state

The office owns the physical load. The driver **views the manifest and
confirms they've checked it** — an acknowledgement + timestamp, **not a
gate**. It does not block `depart` (a broken confirm flow must never strand a
driver mid-route). Its value: accountability, visibility, and it gives the
driver app the loaded quantities the empties validation needs.

Mirrors how cash-handover was built: a read screen + a confirm action + a
Today nudge, no route-lifecycle change.

---

## Stage 1 — Backend

- **`delivery.route`** gains:
  - `loaded_lines` — JSONB, `[{cylinder_type_id, quantity}]`, snapshotted by
    `LoadVehicleForRouteUseCase` at the `→ loaded` transition (it already has
    the lines in hand).
  - `load_confirmed_at timestamptz null`.
  - Migration (`down_revision` = current head).
- **Domain** (`domain/delivery/route.py`): `Route.confirm_load(confirmed_by:
  uuid.UUID)` → sets `_load_confirmed_at = now`, `record_event(
  RouteLoadConfirmed(tenant_id, route_id, driver_id, confirmed_by))`. Guard:
  `if self._status != "loaded": raise ValidationError(...)`; idempotent
  no-op if already confirmed.
- **Use case + endpoint**: `ConfirmRouteLoadUseCase`;
  **`POST /routes/{id}/confirm-load`** — `require_permission("routes:deliver")`
  + the driver-ownership check (`route.driver_id != scoped_driver_id → 404`).
  `Idempotency-Key` **optional** via `run_idempotent` (the offline app sends
  one; there's no other caller).
- **Read**: `RouteResponse` gains `loaded_lines: list[RouteLoadLine]`
  (`{cylinder_type_id, cylinder_type_name, quantity}` — join the type name)
  + `load_confirmed_at: datetime | None`. Same on the `GET /routes/active`
  payload.
- **Tests** (`backend/tests/`): load → `loaded_lines` populated; confirm sets
  the timestamp + emits `RouteLoadConfirmed`; confirm on a non-`loaded` route
  → 422; a second confirm is a no-op 200; a different driver → 404; replay
  under the same key is idempotent.
- **Gate:** `uv run pytest`, `ruff check src tests`, `mypy src`,
  `lint-imports`.
- **Commit:** `feat(backend): route load manifest + driver load-confirmation`

### ✅ DONE 2026-09-03

- Domain (`domain/delivery/route.py`): `LoadedLine` VO;
  `RouteLoadConfirmed` event (`route_id, tenant_id, driver_id, confirmed_by`);
  `Route` gained `_loaded_lines` / `_load_confirmed_at` (in `__slots__` +
  `__init__`), `loaded_lines` / `load_confirmed_at` properties,
  `record_load_manifest(lines)` and `confirm_load(confirmed_by)` (idempotent;
  `InvariantViolation` if not `loaded`).
- App: `LoadVehicleForRouteUseCase` calls `record_load_manifest([...])` after
  `change_status("loaded")`. New `ConfirmRouteLoadCommand`
  (`route_id, confirmed_by, expected_driver_id`) + `ConfirmRouteLoadUseCase`
  (`NotFoundError` for a missing route **or** `expected_driver_id` mismatch).
- Persistence: `RouteModel` gained `loaded_lines` (JSONB) + `load_confirmed_at`;
  repo `save()`/`_to_domain()` round-trip both. Migration `b3e1d7a24f90`
  (`down_revision = a7f1c93e6b20`), applied to `lpg_dev` + `lpg_test`.
- API: `POST /routes/{id}/confirm-load` (`routes:deliver`, `run_idempotent`
  with an **optional** key, `_resolve_read_scope` → `expected_driver_id`).
  `RouteResponse` + `GET /routes/active` gained `loaded_lines`
  (`RouteLoadLineResponse` = `{cylinder_type_id, quantity}`) + `load_confirmed_at`.
- **Deviations from the plan:**
  - "not loaded" → **409 `INVARIANT_VIOLATION`**, not 422 — the codebase maps
    every `DomainError` to 409 (well-formed request, wrong state), same as an
    illegal `change_status`.
  - `loaded_lines` carries **`{cylinder_type_id, quantity}` only** — no
    `cylinder_type_name`. The domain VO has no name and the read model would
    need a join; the Driver App resolves names client-side (Stage 3 adds a
    cached cylinder-type lookup). Simpler + more offline-friendly.
- Tests: `test_domain_route.py::TestVanLoad` (4); `test_route_use_cases.py`
  `TestConfirmRouteLoadUseCase` (4) + a manifest-snapshot assertion on the
  load test; `test_route_endpoints_smoke.py` — `confirm-load` in the
  lifecycle test (manifest + confirm + idempotent replay) + 2 focused tests
  (409 before loaded, 404 for another driver's route).
- Gate: `uv run pytest` **1140 passed**; ruff / mypy src / lint-imports (5/5)
  clean.
- **Precursor:** `d4c2ded` fixed `driver_app/pubspec.yaml` — `cb8a7b0` (icons)
  had displaced the `drift` dev-dep into the `flutter_launcher_icons:` block,
  breaking `flutter analyze`.

## Stage 2 — `packages/api_client`

- `RouteApi.confirmLoad(String routeId) → Result<RouteSummary>` (`POST
  /api/v1/routes/$routeId/confirm-load`, sends an `Idempotency-Key`).
- `RouteSummary` gains `loadedLines: List<RouteLoadLine>` +
  `loadConfirmedAt: DateTime?`; new `RouteLoadLine` (`cylinderTypeId`,
  `quantity` — names resolved client-side). `bool get isLoadPending =>
  status == 'loaded' && loadConfirmedAt == null`.
- Tests: parse `loaded_lines`; `confirmLoad` posts to the right path with a key.
- **Commit:** `feat(mobile): RouteLoadLine model + RouteApi.confirmLoad`

### ✅ DONE 2026-09-03

- `models/route_models.dart` — `RouteLoadLine` (`cylinderTypeId`, `quantity`);
  `RouteSummary` gained `loadedLines` (defaults `const []`) + `loadConfirmedAt`,
  parsed from `loaded_lines` / `load_confirmed_at`; `bool get isLoadPending
  => status == 'loaded' && loadConfirmedAt == null`. Both new ctor params are
  optional — existing `RouteSummary(...)` call sites (screen-test fixtures)
  are untouched.
- `route_api.dart` — `RouteApi.confirmLoad(routeId, {idempotencyKey}) →
  Result<RouteSummary>` (`POST /routes/{id}/confirm-load`, sends
  `Idempotency-Key`, `Uuid().v4()` default).
- Tests: `route_api_test.dart` +2 (manifest parse + `isLoadPending`;
  `confirmLoad` path/method/header + `loadConfirmedAt`).
- Gate: `api_client` **55** + `driver_app` 70 + `customer_app` 45 pass; all
  analyze clean.

## Stage 3 — Driver app

- **`features/van_load/`**:
  - `data/van_load_provider.dart` — `routeLoadManifestProvider` reads the
    active route (cache-first, already cached as `('route_active','current')`
    by `CacheFirstReader`); no new fetch, just projects `loadedLines` +
    `loadConfirmedAt`. `pendingLoadProvider` (`RouteSummary?`) — the active
    route iff `isLoadPending`, else `null` (mirrors `pendingCashHandoverProvider`).
  - `presentation/van_load_screen.dart` — `ConsumerWidget`. Manifest table
    (`LpgCard` per line: cylinder type name · "×N"), route date, "N stops",
    a total. `LpgButton "Confirm load"` → `deliveryMutationsProvider.confirmLoad(...)`;
    on success snackbar + `context.go('/')`. If `loadConfirmedAt != null` →
    a "Load confirmed <date>" receipt state.
- **Route**: `GoRoute(path: 'routes/:routeId/load', name: 'vanLoad', …)` nested
  under the **Deliveries** branch (next to `cash-handover`), so the bottom
  bar stays — see `[26]`'s routing note / `reference_driver_app_routing`.
- **Today nudge** (`today_screen.dart`) — a `_PendingLoadCard` shown when
  `ref.watch(pendingLoadProvider).value != null`, above the route section
  (like `_PendingCashCard`): "Check your van load — N cylinders for today's
  route" → `context.goNamed('vanLoad', pathParameters: {'routeId': …})`.
- **`DeliveryMutations.confirmLoad(routeId)`** — queued op `route_confirm_load`,
  payload `{path: '/api/v1/routes/$routeId/confirm-load', body: null,
  aggregateId: routeId}`; optimistic (no cached-status change — the screen
  flips to the receipt via `pendingSyncAggregatesProvider`, same as
  cash-handover). `SyncCoordinator._dispatch` gains the `route_confirm_load`
  case (thin `{path, body}` — no special handling).
- **Tests**: manifest renders; "Confirm load" queues a `route_confirm_load`
  op; pending nudge shows only when `isLoadPending`; the offline harness
  covers the queue path.
- **Commit:** `feat(mobile): van-load manifest screen + confirm (queued)`

### ✅ DONE 2026-09-03

- **`features/van_load/data/van_load_provider.dart`** (new):
  - `cylinderTypeNamesProvider` (`FutureProvider<Map<String,String>>`) —
    cache-first `GET /api/v1/admin/cylinder-types` via a new
    `CacheFirstReader.getList` (best-effort JSON-array reader, never throws);
    that endpoint has **no permission gate**, so the driver token works.
  - `routeLoadProvider` (`.autoDispose.family<VanLoad, routeId>`) — projects
    the active route's `loadedLines` into `VanLoadLine`s with resolved names
    (falls back to the id's first 8 chars); throws if the route is no longer
    active. `VanLoad` exposes `isConfirmed` + `totalCylinders`.
  - `pendingLoadProvider` (`.autoDispose<RouteSummary?>`) — the active route
    iff `isLoadPending` **and** not already queued
    (`pendingSyncAggregatesProvider`), else `null`.
- **`presentation/van_load_screen.dart`** (new) — `ConsumerWidget`; manifest
  `LpgCard` (per line `label · ×N`, divider, total), a `_ConfirmedBanner` when
  `load.isConfirmed || queued`, else an `LpgButton "Confirm load"` →
  `deliveryMutationsProvider.confirmLoad(routeId)` → invalidate
  `activeRouteProvider`/`pendingLoadProvider` → snackbar + `context.go('/')`.
- **`offline/delivery_mutations.dart`** — `confirmLoad(routeId)`: stamps
  `load_confirmed_at` on the cached `('route_active','current')` when it
  matches, then `enqueueOperation('route_confirm_load', {path, body: null,
  aggregateId: routeId})`.
- **`sync_engine` `SyncCoordinator._dispatch`** — `route_confirm_load` joins
  the thin structured-op group (`{path, body}`, no special handling).
- **Routing** — `GoRoute('routes/:routeId/load', name: 'vanLoad')` under the
  Deliveries branch, after `cashHandover`.
- **Today nudge** — `_PendingLoadCard` (watches `pendingLoadProvider`) above
  the pending-cash block: "Check your van load — N cylinders for today's
  route" → `goNamed('vanLoad')`.
- **`api_provider.dart`** — `cylinderTypeApiProvider`; **`cached_resource.dart`**
  — `getList(path, {type, id})`.
- **Deviation:** `cylinderTypeNamesProvider` uses a cache-first raw-array read
  rather than a typed `CylinderTypeApi` call, so the name lookup survives
  offline (the endpoint response is cached on first online open).
- Tests: `van_load_screen_test.dart` (3 — manifest renders resolved names +
  totals; Confirm queues `route_confirm_load` + navigates home;
  already-confirmed shows the notice, no button — overrides
  `pendingSyncAggregatesProvider` with a plain stream so `pumpAndSettle`
  doesn't hang on the live drift watch); `delivery_mutations_test.dart` +1
  (stamps the cache + queues); `today_screen_test.dart` +1 (nudge shows);
  `sync_coordinator_test.dart` +1 (routes to the structured path).
- Gate: `sync_engine` **15** · `api_client` **55** · `driver_app` **75** pass;
  `flutter analyze` clean for `sync_engine` + `driver_app`.

## Stage 4 — Client-side empties validation

- `record_delivery_screen.dart` `_QuantityRow` for `quantityCollectedEmpty`:
  cap at `quantityDelivered` for that line (you can't hand back more empties
  than fulls delivered), and warn (not block) if the route's running
  `sum(quantityCollectedEmpty)` would exceed the manifest total for that
  cylinder type. Manifest comes from `routeLoadManifestProvider` (cached, so
  it works offline).
- Arch doc §2: "client-side check that a driver isn't recording more empties
  collected than physically loaded, before it ever reaches the server."
- Tests: the `_QuantityRow` stepper clamps; an over-manifest total shows the
  warning.
- **Commit:** `feat(mobile): cap empties-collected against the van load`

### ✅ DONE 2026-09-03

- **`offline/pending_sync.dart`** — `queuedEmptiesByTypeProvider`
  (`StreamProvider<Map<String,int>>`) sums `quantity_collected_empty` across
  every unsynced `order_deliver` op, keyed by cylinder-type id.
- **`record_delivery_screen.dart`** — build reads the active route's
  `loadedLines` into a `manifest` map + `queuedEmptiesByTypeProvider`; each
  `_QuantityRow` gets `loadedForType` + `emptiesQueuedElsewhere`. When
  `emptiesQueuedElsewhere + collected > loadedForType` it shows an amber
  `warning_amber_rounded` row ("more empties than the van was loaded with for
  this type (N loaded). Recheck before you submit.") — **soft**, never blocks
  submit. No manifest for a type ⇒ no warning.
- The existing hard caps stay: Delivered stepper `max: ordered`, Empties
  stepper `max: delivered` (you still can't record more empties than fulls
  delivered at a stop).
- **Deviations:**
  - The running tally counts **queued** deliveries only — a synced delivery
    has already cleared the server and its order is no longer in the driver's
    local data. Early in a route the warning can under-count; acceptable for a
    soft check.
  - No new domain VO (`CylinderBalance`) — a `Map<typeId,int>` off the manifest
    + queue is enough for this one check; a VO can come later if more
    client-side inventory rules appear.
- Tests: `record_delivery_screen_test.dart` +2 (warning shows when prefilled
  empties exceed a 1-cylinder manifest and clears when stepped down;
  no warning when `queued elsewhere + this stop ≤ loaded`); `_container` now
  overrides `activeRouteProvider` + `queuedEmptiesByTypeProvider` (plain
  stream, so `pumpAndSettle` doesn't hang on the live queue watch).
- Gate: `driver_app` **77** pass; `flutter analyze` clean.

## Stage 5 — (optional) office notification

- `RouteLoadConfirmed` → `notification_handlers.py` enqueues
  `route_load_confirmed_staff` → `notification_jobs.py` in-app-only to
  `_STAFF_ALERT_ROLES` ("Driver X confirmed the load for route #Y"). Follows
  the `cash_shortfall_staff` pattern exactly.
- **Commit:** `feat(backend): notify dispatch when a driver confirms the van load`

## Stage 6 — Emulator + docs

- Emulator round-trip: office loads a route (dashboard or seeded) → driver
  Today shows the van-load nudge → open → manifest matches → Confirm →
  receipt, nudge gone. Airplane-mode confirm → queued → drains.
- `27-van-load-confirmation/STATUS.md`; update `24-driver-app-shell/STATUS.md`;
  memory (`reference_van_load_confirmation.md` or fold into
  `reference_driver_offline_sync` / a driver-app-features note).

---

## Risks / notes

- **`loaded_lines` snapshot vs. the load transfer** — snapshotting on the
  route at `→ loaded` is simpler and stable than deriving from inventory
  transactions later; the transfer already computed these exact lines.
- **Route re-load / top-up** — if BR-12 ever allows loading a route twice,
  `loaded_lines` must be additive and `load_confirmed_at` should reset. Out
  of scope unless that path exists today (it doesn't — `load` only accepts
  `planned`).
- **Not a depart gate** — deliberately. If the office wants a hard gate
  later, add `RouteLoadConfirmed`-required to `DepartOrderUseCase`'s
  `loaded → in_progress` guard; it's a one-line domain change on top of this.
- **`cylinder_type_name`** in the manifest needs a join in the read model —
  the driver app has no cylinder-type lookup of its own.

## References

- `docs/architecture/15-architecture-decision-records.md` — BR-12 (route
  loading), D-24 (offline-first, §2 offline validation)
- Phase 24 [`STATUS.md`](../24-driver-app-shell/STATUS.md),
  Phase 26 [`STATUS.md`](../26-driver-offline-sync/STATUS.md) — the delivery
  workflow + the queue/cache-first infra this builds on
- `planning/features/24-driver-app-shell/CASH_HANDOVER.md` — the pattern this
  mirrors
