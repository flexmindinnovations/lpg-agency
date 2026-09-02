# Status: Driver App Shell & Design-System Parity

**Phase:** 24
**Status:** Feature-complete — Stages A–D2 done, delivery workflow regression-tested on device

## Context

The Driver App was assembled piecemeal across Phases 5/6/12 and the Phase-19
live-tracking work and never got the shell pass the Customer App got: raw
`TextField` login, no splash, single-screen (no bottom nav), no profile
screen, **no way to log out at all**, no delivery history.

## Progress

| Stage | State |
|---|---|
| A — Splash + themed login | ✅ Done — `SplashScreen` + `/splash` route gate, `login_screen.dart` rewritten with `LpgCard`/`LpgTextField`/`LpgButton` + branding + validation + version footer; logo asset wired; 27 tests pass, analyze clean; login verified on emulator |
| B — Shell + 3-tab navigation | ✅ Done — `StatefulShellRoute` + `AppShell` (Today / Deliveries / Profile); `ActiveDeliveryScreen` split into `TodayScreen` (progress + next stop + location card) and `DeliveriesScreen` (stop list + Past routes history); `LocationSharingCard` / `StopTile` extracted; `RouteApi.listRoutes` + `routeHistoryProvider`; stop/deliver routes moved above the shell; minimal Profile tab with the app's first **Log Out**. 31 tests pass, analyze clean, APK builds |
| C1 — Backend `GET /drivers/me` | ✅ Done — `DriverMeResponse` / `DriverMeVehicle`; endpoint resolves driver from token → employee (name/phone) + active route → vehicle; declared before `/drivers/{driver_id}`. Integration test (driver reads own profile; non-driver → 404). ruff / mypy / lint-imports clean; 752 unit + driver/route smoke pass |
| C2 — Profile tab enrichment | ✅ Done — `DriverApi.getMe` + `DriverMe`/`DriverMeVehicle` models + `driverProfileProvider`; `ProfileScreen` shows name / phone / licence / vehicle / status + Log Out + version; `main.dart` docstring refreshed. 34 driver + 48 api_client tests pass, analyze clean |
| D — Emulator verification | ✅ Done — full shell verified live on emulator-5554 against real backend data: **Today** (active route "1 of 2 delivered" + progress bar, next-stop card, location-sharing), **Deliveries** (current stops with status icons + "Past routes" history — completed ×2, cancelled), **Profile** (name/phone/licence/vehicle "TS07UB4412 · Tata Ace Gold"/status from `GET /drivers/me`, Log Out). Splash + themed login verified in Stage A. The dev backend had to be restarted first — `uvicorn --reload` was serving pre-Stage-C1 code (known Windows flakiness). |
| D2 — Delivery-workflow regression | ✅ Done 2026-09-02 — full **depart → record delivery** run on emulator-5554 against seeded e2e driver (`e2e.driver@example.com`, route `5d5bf7a9`): tap next-stop from **Today** → StopDetail (top-level route, no bottom nav) → "Start this delivery" (`ready_for_dispatch → out_for_delivery`) → "Record delivery" (`/stops/:id/deliver`) → cylinders/payment/OTP (read from `dev:otp-inbox`)/signature/photo → "Confirm delivery" → **lands back on Today, "2 of 7 delivered"**, next stop advances. Also verified: Deliveries-list → StopDetail nav, failed-delivery bottom sheet (`out_for_delivery → failed_delivery`, screen shows the "nothing to do" state), StopMapCard renders LocationIQ `streets` tiles + geocoded "approximate" banner. **Two restructure bugs found & fixed** — see below. |

## Regression fixes (2026-09-02)

The Stage-B restructure (stop/deliver routes lifted above the shell) introduced
two bugs, both caught by the D2 on-device run and fixed:

1. **Stranded after recording a delivery.** `RecordDeliveryScreen` popped back to
   `StopDetailScreen`, which re-fetched the now-`delivered` order — but a
   delivered order drops out of the driver's `_resolve_scope` visibility (and
   the last stop completes the route), so the screen showed "Could not load this
   stop — No order visible". Fix: on success `RecordDeliveryScreen` now
   `context.go('/')` (back to the route view) instead of `Navigator.pop()`, and
   invalidates `routeHistoryProvider` too.
   [`record_delivery_screen.dart`](../../../mobile/apps/driver_app/lib/src/features/delivery/presentation/record_delivery_screen.dart)
2. **Stop-number off-by-one.** `today_screen.dart` and `stop_tile.dart` rendered
   `Stop ${sequenceNumber + 1}` — but `RouteStop.sequence_number` is 1-based
   (`route.py:313`, `len(stops) + 1`), so stop 1 showed as "Stop 2". Fixed to
   `Stop ${sequenceNumber}`; test fixtures corrected from the bogus 0-based
   assumption.

## Follow-ups landed after the shell

- **Route map on Stop Detail** (`16d822c` extract `packages/maps`, next commit
  the driver feature): `LocationMap` + LocationIQ `GeocodingService` moved into
  a shared `mobile/packages/maps`; the driver Stop Detail screen now shows a
  `StopMapCard` — destination pin (pinned coords, else geocoded with an
  "approximate" banner), the driver's own position marker, a recenter FAB, and
  a **Navigate** button that opens Google/Apple Maps. Verified on the emulator
  (map renders LocationIQ tiles; Navigate launches Google Maps).

## Follow-on work (planned, not started)

- **Cash-handover screen** — [CASH_HANDOVER.md](./CASH_HANDOVER.md). Driver
  end-of-route cash declaration; needs a backend read endpoint +
  double-declare guard first. The largest remaining gap in the driver
  delivery workflow after the shell.

## Notes

- Plan: [PLAN.md](./PLAN.md) · Tasks: [TASKS.md](./TASKS.md)
- Delivery feature screens (Active Delivery, Stop Detail, Record Delivery) were
  already design-system-themed before this phase.
- Driver push notifications remain out of scope.
- Driver app now needs a `dart_defines.local.json` (gitignored; see the
  `.example`) with `LOCATIONIQ_API_KEY` for production-grade map tiles +
  geocoding — degrades to OSM/Nominatim without it.

## Last Updated

2026-09-02 — Stage D2 delivery-workflow regression on emulator; fixed the
post-delivery navigation strand + the stop-number off-by-one.
