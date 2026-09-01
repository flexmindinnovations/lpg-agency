# Driver App Shell — Tasks

## Stage A — Splash + themed login
- [ ] `splash_screen.dart` (ported from customer app, "Driver" subtitle)
- [ ] Copy `assets/images/lpg_app_logo.jpg`; wire `flutter: assets:` in pubspec
- [ ] `router.dart`: `/splash` route, `initialLocation`, `AuthStatus.unknown` redirect
- [ ] Rewrite `login_screen.dart` widget tree (LpgCard/LpgTextField/LpgButton, branding, validation, version footer); keep OTP logic
- [ ] `login_screen_test.dart` (new); update `widget_test.dart`

## Stage B — Shell + tabs
- [ ] `app_shell.dart` (3-tab `NavigationBar`)
- [ ] `today_screen.dart` (route summary + next stop + location-sharing card)
- [ ] `deliveries_screen.dart` (stop list + "Past routes")
- [ ] Extract `LocationSharingCard` + `StopTile` shared widgets
- [ ] Delete `active_delivery_screen.dart`
- [ ] `router.dart`: `StatefulShellRoute`, move `stops/:orderId` + `deliver` under `/deliveries` (keep route names)
- [ ] `routeHistoryProvider`; `RouteApi.listRoutes({status})` + model parse
- [ ] Tests: `app_shell_test`, `today_screen_test`, `deliveries_screen_test`; rework `active_delivery_screen_test`; update `widget_test`; `route_api_test`

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
