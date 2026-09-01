# Driver App Shell — Tasks

## Stage A — Splash + themed login ✅
- [x] `splash_screen.dart` (ported from customer app, "Driver" subtitle)
- [x] Copy `assets/images/lpg_app_logo.jpg`; wire `flutter: assets:` in pubspec
- [x] `router.dart`: `/splash` route, `initialLocation`, `AuthStatus.unknown` redirect
- [x] Rewrite `login_screen.dart` widget tree (LpgCard/LpgTextField/LpgButton, branding, validation, version footer); keep OTP logic
- [x] `login_screen_test.dart` (new); update `widget_test.dart`

## Stage B — Shell + tabs ✅
- [x] `app_shell.dart` (3-tab `NavigationBar`)
- [x] `today_screen.dart` (route summary + next stop + location-sharing card)
- [x] `deliveries_screen.dart` (stop list + "Past routes")
- [x] Extract `LocationSharingCard` + `StopTile` shared widgets
- [x] Delete `active_delivery_screen.dart`
- [x] `router.dart`: `StatefulShellRoute`; `stops/:orderId` + `deliver` moved **above** the shell (full-screen drill-in reachable from any tab), route names kept
- [x] `routeHistoryProvider`; `RouteApi.listRoutes({status})` + `RouteSummary.date`
- [x] Minimal Profile tab (`profile_screen.dart`) with Log Out — enriched in C2
- [x] Tests: `app_shell_test`, `today_screen_test`, `deliveries_screen_test`; deleted `active_delivery_screen_test`; updated `widget_test`; `route_api_test`

## Stage C1 — Backend `GET /drivers/me`
- [ ] `DriverMeResponse` / `DriverMeVehicle` schema
- [ ] `GET /drivers/me` endpoint (before `/drivers/{driver_id}`), `drivers:read`
- [ ] `test_driver_endpoints_smoke.py` + `test_driver_rbac.py` coverage
- [ ] ruff / mypy / lint-imports green

## Stage C2 — Profile tab
- [ ] `driver_api.dart` (`DriverApi.getMe`) + `driver_models.dart` + barrel export
- [ ] `driverApiProvider`, `driverProfileProvider`
- [ ] `profile_screen.dart` (identity, vehicle, status, Log Out, version)
- [ ] `main.dart` docstring refresh
- [ ] `profile_screen_test.dart`

## Stage D — Verification
- [ ] Emulator walkthrough (splash → login → Today → Deliveries → Profile → Log Out)
- [ ] Screenshots; STATUS.md + MODULE_STATUS.md
