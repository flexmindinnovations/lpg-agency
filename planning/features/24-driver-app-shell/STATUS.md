# Status: Driver App Shell & Design-System Parity

**Phase:** 24
**Status:** In Progress — Stages A & B complete, Stage C next

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
| C1 — Backend `GET /drivers/me` | ⬜ Not started |
| C2 — Profile tab enrichment | ⬜ Not started |
| D — Emulator verification | ⬜ Not started |

## Notes

- Plan: [PLAN.md](./PLAN.md) · Tasks: [TASKS.md](./TASKS.md)
- Delivery feature screens (Active Delivery, Stop Detail, Record Delivery) were
  already design-system-themed before this phase.
- Driver push notifications remain out of scope.

## Last Updated

2026-09-01 — phase opened, Stage A started.
