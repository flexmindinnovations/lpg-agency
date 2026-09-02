# Plan: Driver app push notifications

**Phase:** 25
**Status:** Phases A–B done 2026-09-02 (verified end-to-end on emulator) · Phases C–D pending
**Drafted:** 2026-09-02

---

## Context

The driver app has **no push notifications** — no `firebase_messaging`, no
FCM token registration. The customer app has had FCM live since 2026-08-31
(Firebase project `lpg-erp-2b143`, verified end-to-end). A driver only learns
about a new route / stop by opening the app and pull-to-refreshing.

**The backend is mostly ready:**

- `POST /api/v1/notifications/devices` — role-agnostic, scoped by
  `principal.user_id`. A driver token registers exactly like a customer one.
  Migration `f3a9c1e07b42` (device_token) is applied.
- The shared `packages/api_client` `NotificationApi` already has
  `registerDevice` / `unregisterDevice` / `getMyNotifications` /
  `getUnreadCount` / `markRead` / `markAllRead`.
- `driver_assigned` (fires on `OrderAssignedToRoute`) is **already wired for
  push** ([`notification_jobs.py`](../../../backend/src/lpg/infrastructure/jobs/notification_jobs.py):
  `_should_send_push` + `_should_send_sms`), and its recipient resolution
  (order → `route_stop` → route → `driver.identity_user_id`) already targets
  the driver. So the moment the driver app registers a token, "you've been
  assigned to deliver order #X" starts arriving.
- Backend FCM credentials (`LPG_FCM_CREDENTIALS_PATH` → the gitignored
  service-account JSON) work for the whole `lpg-erp-2b143` project — no
  backend push-channel change needed.

**The gap that needs a human:** the driver Android app
(`com.lpgagency.driver_app`) is not registered in the Firebase project.
Someone with the `moimssab@gmail.com` Google account must run
`flutterfire configure` for `driver_app` (or add the Android app in the
Firebase console and download `google-services.json`).

---

## Phase A — Client FCM plumbing (no backend change)  ✅ DONE 2026-09-02

**Verified end-to-end on `emulator-5554`:** app launches with Firebase (no
crash) → login → FCM token → `POST /notifications/devices` → real
`notification.device_token` row (platform `android`). Then enqueued a
`driver_assigned` job → real FCM v1 push → **tray notification "New Delivery
Assigned — order #D7E0D53F"** → tapped it → deep-linked to `/stops/{orderId}`
(Stop Detail for ORD000030). `notification_log`: push `sent`, sms `sent`.

- **A0** — `flutterfire configure --project=lpg-erp-2b143 --platforms=android
  --android-package-name=com.lpgagency.driver_app` (done via the CLI, which
  was already authed for `moimssab@gmail.com`). Registered the Android app
  (`1:173792123388:android:a78bb96bb3efecf97b3a79`), committed
  `android/app/google-services.json`, `lib/firebase_options.dart`,
  `firebase.json`; it also added the `com.google.gms.google-services` plugin
  to both gradle files (bumped `4.3.15` → `4.4.2` to match customer_app).
- **A1** — **Decision: copied** `PushNotificationService` into
  `driver_app/lib/src/push/` (not extracted to `packages/push` — one file,
  the only divergence is the route resolver, and extraction would re-test a
  working customer_app for marginal gain). Route resolver is now the
  top-level testable `driverRouteFromData` (`order` → `/stops/$id`, `route`
  → `/`, else Today, empty → null). `registerWithBackend` / `unregister` now
  swallow a missing-FCM error via `_tokenOrNull` — logout must not depend on
  push. Follow-up: dedupe with customer_app into `packages/push`.
- **A2** — pubspec: `firebase_core ^3.8.0`, `firebase_messaging ^15.1.5`,
  `flutter_local_notifications ^18.0.1`. gradle: `isCoreLibraryDesugaringEnabled`,
  `minSdk = maxOf(flutter.minSdkVersion, 23)`, `coreLibraryDesugaring(...)`.
  Manifest: `default_notification_channel_id` → `lpg_default_channel`
  (`POST_NOTIFICATIONS` was already there from Step D).
- **A3** — `main.dart`: `Firebase.initializeApp()` +
  `onBackgroundMessage` + `pushService.init()` in try/catch, then
  `_wirePushRegistrationToAuth`. `api_provider.dart`: `notificationApiProvider`
  + `pushNotificationServiceProvider`. `DriverApp` → `ConsumerStatefulWidget`
  with the tap-route subscription (`ref.read(routerProvider).go`). Profile
  "Log Out" → `unregister()` then `logout()`.
- **A4** — `test/push/push_notification_service_test.dart` (5 cases for
  `driverRouteFromData`). `widget_test.dart` + `profile_screen_test.dart`
  `_host`/`_appWith` gained a `pushNotificationServiceProvider` override.
  driver_app: 49 tests pass, analyze clean.

**Known limitation** (Phase B fixes): `driver_assigned` is per-order —
assigning a 7-stop route in one dispatcher action = 7 pushes + 7 SMS.

<details><summary>Original Phase A plan (for reference)</summary>

### A1. `PushNotificationService` — extract or copy

`customer_app/lib/src/push/push_notification_service.dart` is ~200 lines: FCM
permission, token registration, `onTokenRefresh`, foreground display via
`flutter_local_notifications`, a `Stream<String>` of tap-routes, and
`takeInitialRoute()` for a cold start. The only app-specific part is
`_routeFromData` (customer routes).

**Decision:** extract the lifecycle into **`packages/push`** with an injected
`String? Function(Map<String, dynamic> data)` route resolver — both apps
consume it, customer_app's copy is deleted. (Precedent: `packages/maps`.)
Alternative: copy into `driver_app` and diverge; smaller diff, more drift.

Driver route resolver:
```dart
String? _driverRoute(Map<String, dynamic> data) {
  final refType = data['reference_type'] as String?;
  final refId = data['reference_id'] as String?;
  if (refType == 'order' && refId != null) return '/stops/$refId';
  return null; // no /notifications screen in v1 — see Phase D
}
```

### A2. `driver_app` deps + Android config

- `pubspec.yaml`: `firebase_core: ^3.8.0`, `firebase_messaging: ^15.1.5`,
  `flutter_local_notifications: ^18.0.1` (match customer_app).
- `android/app/build.gradle.kts`: `id("com.google.gms.google-services")`,
  `minSdk = maxOf(flutter.minSdkVersion, 23)`, `coreLibraryDesugaring(...)`.
- `android/settings.gradle.kts`: the `com.google.gms.google-services` plugin.
- `AndroidManifest.xml`: `default_notification_channel_id` meta-data
  (`lpg_default_channel`). `POST_NOTIFICATIONS` is already declared (added for
  the foreground location service in Step D).

### A3. Wire into `main.dart` + `DriverApp`

- `main.dart`: `Firebase.initializeApp()` + `FirebaseMessaging.onBackgroundMessage`
  + `pushService.init()`, all in a `try/catch` (a missing config must not
  crash the app), then `_wirePushRegistrationToAuth(authController,
  pushService)` — register on the first authenticated transition, mirroring
  customer_app.
- `api_provider.dart`: `notificationApiProvider` (new — driver_app doesn't
  have one yet).
- `DriverApp` `ConsumerWidget` → `ConsumerStatefulWidget`: subscribe to
  `pushService.taps` → `ref.read(routerProvider).go(route)`; handle
  `takeInitialRoute()` after the first frame. Copy `_CustomerAppState`.
- Profile "Log Out" → `await pushService.unregister()` before
  `authController.logout()` (so a shared device stops getting the previous
  driver's pushes). The Profile screen already calls `logout()`.

### A4. Tests

- `packages/push` (if extracted): the existing customer_app push tests move
  here; add a driver-route-resolver test.
- `driver_app`: a widget test that a tap-route from the push stream drives
  `router.go` (mirror `customer_app/test/widget_test.dart`'s push case).
- The registration-on-auth wiring: unit test `_wirePushRegistrationToAuth`.

### A5. Emulator verification

`emulator-5554`, seeded e2e driver, real FCM (backend has credentials):
assign an order to the driver's route from the dashboard → `driver_assigned`
job → tray notification on the emulator → tap → lands on `/stops/{orderId}`.
Check `notification.notification_log` has a `channel='push'` `sent` row.

</details>

---

## Phase B — Backend: route-level "route ready" push  ✅ DONE 2026-09-02

**Verified live** (backend + arq restarted with the change, driver app from
Phase A still on `emulator-5554`): enqueued a `route_ready` job for the e2e
driver's route → in-app *"Route Ready — Your route is ready — 7 stops."*
(`reference_type: route`) + push `sent`, no SMS → tapped the tray
notification → landed on the Today tab. Enqueued a `driver_assigned` for an
order on that (`in_progress`) route → push `sent`, **no SMS row** (the
demotion).

- **B1** — `RouteStatusChanged` gained `tenant_id` + `driver_id` (from the
  `Route` aggregate); both `record_event(RouteStatusChanged(...))` sites in
  `route.py` updated. The realtime handler only reads `event.route_id`, so
  untouched. Domain test asserts the fields propagate.
- **B2** — `_on_route_status_changed` (was a stub): on `new_status ==
  "loaded"` → enqueue `{type: "route_ready", tenant_id, driver_id,
  route_id}`. **Trigger is `loaded`, not `in_progress`** — the office loads
  the van (`POST /routes/{id}/load`), then the driver's first `depart` moves
  it `loaded → in_progress` (`DepartOrderUseCase`), so `loaded` is exactly
  "ready, waiting for the driver". `notification_jobs.py` `route_ready`
  branch resolves `driver.identity_user_id`, counts stops (job stuffs
  `stop_count` into the payload for `_get_body`), sends in-app + push only.
- **B3** — `driver_assigned` dropped from `_should_send_sms` entirely and
  from `_should_send_push`; the job now computes `send_email/sms/push` once
  before the recipient loop, and for `driver_assigned` sets
  `send_push = (route.status == "in_progress")`. A still-planned/loaded
  route's assignments are in-app only — the one `route_ready` push covers
  them.
- **B4** — `test_infrastructure_notification_handlers.py` +2 (`loaded`
  enqueues `route_ready`; other statuses enqueue nothing).
  `test_infrastructure_notification_jobs.py` +2 (`route_ready` title/body/
  channels; `driver_assigned` push/SMS both `False` now).
  `test_domain_route.py` asserts the new event fields. 766 unit pass.

<details><summary>Original Phase B plan (for reference)</summary>

### B1. `RouteStatusChanged` carries tenant + driver

Today it's `{route_id, old_status, new_status}` only — which is exactly why
`_on_route_status_changed` is a `pass` with a wall of TODO comments (a thin
handler can't resolve the driver/tenant). Add `tenant_id` and `driver_id`
(the `Route` aggregate has both). Update the realtime handler that also
consumes it (`register_realtime_handlers`).

### B2. `_on_route_status_changed` → `route_ready` job

On `new_status in {"loaded", "in_progress"}` (decide which — `loaded` =
"vehicle packed, get going"; `in_progress` = after the driver departs, too
late): enqueue `{type: "route_ready", tenant_id, driver_id, route_id}`.

`notification_jobs.py` `route_ready` branch: resolve `driver.identity_user_id`,
count the route's stops, in-app + push (no SMS): *"Your route is ready — N
stops."*, `reference_type: "route"`, `reference_id: route_id`. Driver route
resolver maps `route` → the Today tab (`/`).

### B3. Demote per-order `driver_assigned` for drivers

Make `driver_assigned` push/SMS fire only when the order is added to a route
that's **already `in_progress`** (a genuine mid-route addition the driver
must know about now). For a `planned` route, keep it in-app only — the
`route_ready` push covers the batch. Needs the job to check the route status
in the `driver_assigned` branch.

### B4. Tests

Handler enqueues `route_ready` with the right payload on `loaded`; job
title/body/channels; `driver_assigned` push suppressed for a `planned` route,
sent for an `in_progress` one.

</details>

---

## Phase C — Backend: stop-cancelled push

`BookingCancelled` (`{order_id, tenant_id, cancelled_by, ...}`) → new
notification handler → if the order is on an active route (`route_stop_id`
set, route `in_progress`) → `stop_cancelled` job → push the route's driver:
*"Stop #X was cancelled — skip it."*, `reference_type: order`. Lower
priority; a driver arriving at a cancelled stop is annoying but recoverable
(the stop detail already shows a non-actionable status).

---

## Phase D — Polish (optional)

- **Notifications inbox screen** in the driver app — `NotificationApi` list
  methods already exist; a 4th tab or a Profile entry. Gives the tap-fallback
  somewhere to land and a history. Not needed for v1 (every push deep-links
  to a stop or the Today tab).
- **iOS** — `flutterfire configure` with `ios`, `GoogleService-Info.plist`,
  APNs `.p8` key, Xcode Push Notifications + Background Modes capability.
  Same blocker as customer_app's pending iOS push.
- **Unread badge** on the shell / a tab (via `getUnreadCount` +
  `realtime` `InAppNotificationCreated`).

---

## Decisions / open questions

| # | Question | Recommendation |
|---|---|---|
| 1 | `packages/push` extraction vs copy into driver_app? | **Extract** — customer_app's copy is deduped, one injected route resolver. |
| 2 | Ship Phase A alone first, or A+B together? | **A alone** — it's the bulk of the work and unblocks real testing; the per-order noise is a known, non-blocking limitation. |
| 3 | `route_ready` trigger: `loaded` or `in_progress`? | `loaded` — the driver should get "go" before departing, not after. |
| 4 | Keep `driver_assigned` **SMS**? | Demote to in-app-only for `planned` routes in Phase B (SMS per stop is expensive); keep push+SMS for `in_progress` additions. |
| 5 | New feature dir `25-…` or fold into Phase 24? | New dir — it's a distinct capability with its own backend work. |

## Risks / notes

- **A0 is a hard human blocker.** Nothing testable ships until the driver app
  is in the Firebase project.
- Firebase `try/catch` in `main()` is load-bearing — a driver on a device
  without Play Services must still get a working app.
- `firebase_core 3.x` needs `minSdk 23` + core-library desugaring (both
  already required by, and documented in, customer_app's gradle).
- `RouteStatusChanged` field change (B1) touches the realtime handler — grep
  every `RouteStatusChanged` consumer before changing the dataclass.
- Backend `StubPushChannel` (no credentials) logs but sends nothing — the
  emulator won't show a tray notification unless `LPG_FCM_CREDENTIALS_PATH`
  is set (it is, in `backend/.env`, per the customer-app work).
