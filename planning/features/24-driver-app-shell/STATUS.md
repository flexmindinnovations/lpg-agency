# Status: Driver App Shell & Design-System Parity

**Phase:** 24
**Status:** In Progress — Stage A complete, Stage B next

## Context

The Driver App was assembled piecemeal across Phases 5/6/12 and the Phase-19
live-tracking work and never got the shell pass the Customer App got: raw
`TextField` login, no splash, single-screen (no bottom nav), no profile
screen, **no way to log out at all**, no delivery history.

## Progress

| Stage | State |
|---|---|
| A — Splash + themed login | ✅ Done — `SplashScreen` + `/splash` route gate, `login_screen.dart` rewritten with `LpgCard`/`LpgTextField`/`LpgButton` + branding + validation + version footer; logo asset wired; 27 tests pass, analyze clean; login verified on emulator |
| B — Shell + 3-tab navigation | ⬜ Not started |
| C1 — Backend `GET /drivers/me` | ⬜ Not started |
| C2 — Profile tab + logout | ⬜ Not started |
| D — Emulator verification | ⬜ Not started |

## Notes

- Plan: [PLAN.md](./PLAN.md) · Tasks: [TASKS.md](./TASKS.md)
- Delivery feature screens (Active Delivery, Stop Detail, Record Delivery) were
  already design-system-themed before this phase.
- Driver push notifications remain out of scope.

## Last Updated

2026-09-01 — phase opened, Stage A started.
