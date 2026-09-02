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

## Stage C1 — Backend `GET /drivers/me` ✅
- [x] `DriverMeResponse` / `DriverMeVehicle` schema
- [x] `GET /drivers/me` endpoint (before `/drivers/{driver_id}`), `drivers:read`
- [x] `test_driver_endpoints_smoke.py::TestDriverMe` (own profile; non-driver → 404)
- [x] ruff / mypy / lint-imports green

## Stage C2 — Profile tab ✅
- [x] `driver_api.dart` (`DriverApi.getMe`) + `driver_models.dart` + barrel export
- [x] `driverApiProvider`, `driverProfileProvider`
- [x] `profile_screen.dart` (identity, vehicle, status, Log Out, version)
- [x] `main.dart` docstring refresh
- [x] `profile_screen_test.dart` + `driver_api_test.dart`

## Stage D — Verification ✅
- [x] Emulator walkthrough — Today / Deliveries / Profile all verified live against real backend data
- [x] Screenshots captured
- [x] Broader on-device regression of the delivery workflow (depart / record delivery) post-restructure — 2026-09-02; found & fixed the post-delivery navigation strand + stop-number off-by-one (see STATUS "Regression fixes")
