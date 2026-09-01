# Driver App Shell & Design-System Parity — Plan

## Objective

Bring the Flutter Driver App up to the same shell/UX standard the Customer App
reached in Phase 19: a themed splash screen, a design-system OTP login, a
`StatefulShellRoute` bottom-navigation shell, and a way to see your profile
and log out.

## Scope

- **Splash** — a Dart `SplashScreen` shown while the startup session restore
  runs (`AuthStatus.unknown`), gated by the router. No native splash tooling
  (this repo doesn't use `flutter_native_splash`).
- **Login** — rewrite `login_screen.dart` with `LpgCard` / `LpgTextField` /
  `LpgButton`, branded header, styled error banner, phone validation, version
  footer. Keep the existing OTP request/verify logic.
- **Shell** — `StatefulShellRoute.indexedStack` + `AppShell` with a
  `NavigationBar`, 3 tabs:
  1. **Today** — active route at a glance: status, delivered/total progress,
     next stop, live-location-sharing toggle.
  2. **Deliveries** — the current route's stop list (→ Stop Detail → depart /
     Record Delivery) + a "Past routes" history section.
  3. **Profile** — driver name / phone / licence / current vehicle / status,
     **Log Out**, app version.
- **Backend** — `GET /api/v1/drivers/me` returning the calling driver's
  profile + current vehicle, reusing the driver→employee→vehicle resolution
  already written for order tracking.

## Out of scope

- Push notifications for drivers (separate Firebase-wiring follow-up).
- "Cash collected today" on the Today tab (`RouteSummary` carries no amounts).
- Route-history pagination (v1 shows the last ~20 finished routes).
- Offline-first sync-queue for the delivery workflow (its own future phase).

## Stages

| Stage | Content | Commit |
|---|---|---|
| A | Splash screen + themed login + router splash-gate | `feat(mobile): driver app splash + themed login (Stage A)` |
| B | App shell + 3-tab navigation; split `ActiveDeliveryScreen` into Today + Deliveries; `RouteApi.listRoutes` | `feat(mobile): driver app shell + Today/Deliveries tabs (Stage B)` |
| C1 | Backend `GET /drivers/me` + schema + tests | `feat(backend): GET /drivers/me driver self-profile (Stage C1)` |
| C2 | Mobile `DriverApi` + Profile tab + logout | `feat(mobile): driver app Profile tab + logout (Stage C2)` |
| D | Emulator walkthrough; STATUS updates | — |

Gates per stage: `flutter test` + `flutter analyze` for every touched Flutter
package; backend `ruff` / `mypy` / `lint-imports` / `pytest tests/integration/
test_driver_*` for Stage C1. Ask before each commit.
