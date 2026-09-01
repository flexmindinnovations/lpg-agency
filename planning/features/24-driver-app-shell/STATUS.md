# Status: Driver App Shell & Design-System Parity

**Phase:** 24
**Status:** Feature-complete — Stages A–D done; pending broader on-device regression

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

## Follow-ups landed after the shell

- **Route map on Stop Detail** (`16d822c` extract `packages/maps`, next commit
  the driver feature): `LocationMap` + LocationIQ `GeocodingService` moved into
  a shared `mobile/packages/maps`; the driver Stop Detail screen now shows a
  `StopMapCard` — destination pin (pinned coords, else geocoded with an
  "approximate" banner), the driver's own position marker, a recenter FAB, and
  a **Navigate** button that opens Google/Apple Maps. Verified on the emulator
  (map renders LocationIQ tiles; Navigate launches Google Maps).

## Notes

- Plan: [PLAN.md](./PLAN.md) · Tasks: [TASKS.md](./TASKS.md)
- Delivery feature screens (Active Delivery, Stop Detail, Record Delivery) were
  already design-system-themed before this phase.
- Driver push notifications remain out of scope.
- Driver app now needs a `dart_defines.local.json` (gitignored; see the
  `.example`) with `LOCATIONIQ_API_KEY` for production-grade map tiles +
  geocoding — degrades to OSM/Nominatim without it.

## Last Updated

2026-09-01 — phase opened, Stage A started.
