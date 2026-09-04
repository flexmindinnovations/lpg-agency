# Plan: Shared `packages/push`

**Phase:** 28
**Status:** Draft 2026-09-04 · Stages 1–3 pending
**Type:** Non-mandatory tech debt (Phase 25 A1 punt). Pure refactor — no
user-facing behaviour change.

---

## Context

`PushNotificationService` was **copied** into `driver_app/lib/src/push/` in
Phase 25 rather than shared — the A1 decision deferred extraction as
"re-testing a working customer_app for marginal gain". Result: two ~200-line
near-twins:

- `customer_app/lib/src/push/push_notification_service.dart` — 197 L
- `driver_app/lib/src/push/push_notification_service.dart` — 218 L

**The only real divergence:**

| | customer_app | driver_app |
|---|---|---|
| route resolver | `_routeFromData` (private) → `/orders/…`, `/orders/invoices/…`, `/notifications` | `driverRouteFromData` (top-level) → `/deliveries/stops/…`, `/` |
| foreground stream | — | `messages` `Stream<void>` (drives the Alerts unread-badge refetch) |
| token reads | `getToken()` direct | `_tokenOrNull()` — swallows a missing-FCM error so logout never depends on push |

Everything else is byte-identical: `_androidChannelId`/`Name`, `init()`
(permission, `flutter_local_notifications` setup, channel creation, the three
FCM stream subscriptions, `getInitialMessage`), `_sendToken`,
`_showForeground`, `_decodePayload`, `dispose`, and the
`@pragma('vm:entry-point') firebaseMessagingBackgroundHandler`.

Both apps wire it identically: `PushNotificationService(NotificationApi(
apiClient.dio))` in `main()` inside a try/catch,
`FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler)`,
`pushService.init()`, `_wirePushRegistrationToAuth(...)`, then
`pushNotificationServiceProvider.overrideWithValue(pushService)`.

Precedent: **`packages/maps`** (Phase E, `16d822c`) — same "extract a copied
service into a shared package with an injected app-specific hook" shape.

## Design decision — extract, inject the route resolver

- **`PushNotificationService`** moves to `packages/push` unchanged except its
  constructor gains a required
  `String? Function(Map<String, dynamic> data) routeResolver`. `init()` /
  `_emitTapFromData` / `getInitialMessage` call `routeResolver(data)` instead
  of a hard-coded method.
- The **route resolver stays app-side** — it's the one piece that knows app
  routes. `driver_app` keeps `driverRouteFromData`; `customer_app`'s
  `_routeFromData` becomes a public top-level `customerRouteFromData`. Each
  `main()` passes it in:
  `PushNotificationService(api, routeResolver: customerRouteFromData)`.
- **`messages` stream: keep it, always.** Harmless for customer_app (nothing
  listens); `notifications_provider.dart` in driver_app keeps consuming it.
- **`_tokenOrNull` hardening: adopt for both.** Strictly safer — customer_app
  currently can throw on logout if FCM is unavailable. This is the one
  intentional behaviour change; it only affects the missing-FCM edge.
- **`firebaseMessagingBackgroundHandler`** moves into the package and is
  re-exported from the barrel. The `@pragma('vm:entry-point')` is about the
  symbol surviving AOT tree-shaking, not its file — firebase_messaging's own
  docs put handlers in separate files — but this is the one thing that needs
  a **real device check**, not just tests.
- **Native config is not touched** — each app's `android/app/build.gradle`
  desugaring + `google-services` plugin, `AndroidManifest.xml` channel
  metadata, and `firebase_options` / `google-services.json` all stay put.
  Only the Dart service moves.

---

## Stage 1 — Create `packages/push`, migrate customer_app

- **`packages/push/pubspec.yaml`** — `name: push`, `publish_to: none`; deps
  `flutter`, `firebase_messaging: ^15.1.5`,
  `flutter_local_notifications: ^18.0.1`, `api_client: {path: ../api_client}`
  (for `NotificationApi`); dev `flutter_test`, `flutter_lints: ^6.0.0`. (No
  `firebase_core` — the package never calls `Firebase.initializeApp`.)
- **`packages/push/analysis_options.yaml`** —
  `include: package:flutter_lints/flutter.yaml` (matches `maps`).
- **`packages/push/lib/push.dart`** (barrel) — exports
  `src/push_notification_service.dart` (which contains
  `PushNotificationService` + `firebaseMessagingBackgroundHandler`).
- **Move** `customer_app/lib/src/push/push_notification_service.dart` →
  `packages/push/lib/src/push_notification_service.dart`:
  - constructor
    `PushNotificationService(this._notificationApi, {required this.routeResolver})`.
  - delete `_routeFromData`; replace its 3 call sites with `routeResolver(...)`.
  - add the `messages` `Stream<void>` + `_messageController` (tick in
    `_showForeground`, close in `dispose`) — lifted verbatim from the driver
    copy.
  - swap `getToken()` → `_tokenOrNull()` in `registerWithBackend` /
    `unregister`; add `_tokenOrNull`.
- **customer_app**:
  - `pubspec.yaml` — add `push: {path: ../../packages/push}`; **remove**
    `flutter_local_notifications` (only the service used it — verify with
    grep); keep `firebase_core` + `firebase_messaging` (main.dart uses them
    directly).
  - new **`lib/src/push/push_routes.dart`** —
    `String? customerRouteFromData(Map<String, dynamic> data)` (the old
    `_routeFromData` body, made public + top-level).
  - delete `lib/src/push/push_notification_service.dart`.
  - rewrite imports (3 sites): `main.dart`, `src/providers.dart`,
    `test/widget_test.dart` → `import 'package:push/push.dart';` +
    `import 'src/push/push_routes.dart';` where the resolver is referenced.
    `main.dart` constructor call gains `routeResolver: customerRouteFromData`.
- **`melos bootstrap`** (melos globs `packages/**`, so no workspace edit —
  just re-resolve).
- **Gate:** `packages/push` + `customer_app` — `flutter test` +
  `flutter analyze` both clean; customer_app suite (45) identical-green.
- **Commit:** `refactor(mobile): extract packages/push (shared FCM lifecycle)`

## Stage 2 — Migrate driver_app

- **driver_app**:
  - `pubspec.yaml` — add `push: {path: ../../packages/push}`; remove
    `flutter_local_notifications`; keep `firebase_core` + `firebase_messaging`.
  - keep `lib/src/push/push_routes.dart` holding `driverRouteFromData` (move
    it out of the deleted service file).
  - delete `lib/src/push/push_notification_service.dart`.
  - rewrite imports (4 sites): `main.dart`, `src/api_provider.dart`,
    `test/features/profile/profile_screen_test.dart`, `test/widget_test.dart`
    → `package:push/push.dart` + `src/push/push_routes.dart`. `main.dart`
    constructor gains `routeResolver: driverRouteFromData`.
  - `test/push/push_notification_service_test.dart` — it only tests
    `driverRouteFromData`, so it stays in driver_app; retarget its import to
    `src/push/push_routes.dart` and rename to `push_routes_test.dart`.
- **`packages/push/test/push_notification_service_test.dart`** (new) — the
  package's own coverage of the payload→route→stream seam that doesn't touch
  Firebase statics: construct the service with a fake `routeResolver`, feed a
  JSON payload string through the tap path, assert `taps` emits the resolved
  route and a malformed payload emits nothing. (Extract a thin
  `@visibleForTesting handleTapPayload(String)` if the plugin callback can't
  be invoked directly.)
- **Gate:** `packages/push` + `driver_app` — `flutter test` +
  `flutter analyze` clean; driver_app suite (77) green.
- **Commit:** `refactor(mobile): driver_app uses packages/push`

## Stage 3 — Device smoke + docs

- **Emulator** (`emulator-5554`), both apps: debug build, cold start, and —
  the one thing tests can't cover — a **background/terminated-state push**
  (send via the backend or FCM console) to confirm
  `firebaseMessagingBackgroundHandler` still resolves as a `vm:entry-point`
  after the package move, and a **tap deep-link** lands on the right screen
  in each app.
- `28-shared-push-package/STATUS.md`; update
  `25-driver-push-notifications/STATUS.md` +
  `26-driver-offline-sync/STATUS.md` (drop the "`packages/push` dedupe"
  follow-up); memory — fold into `[[driver-push-notifications]]`.

---

## Risks / notes

- **`vm:entry-point` across the package boundary** — the real risk.
  Mitigation: Stage 3's background-push test; if it regresses, the handler
  can stay a top-level function re-declared in each app's `main.dart` that
  delegates to a package function (still removes the duplication that
  matters).
- **customer_app has almost no push test coverage** — `widget_test.dart`
  just constructs the service. Stage 1 leans on `flutter analyze` + the
  Stage 3 emulator smoke as the safety net. This is why Stage 1 is its own
  commit (easy bisect), same rationale as the maps extraction.
- **`flutter_local_notifications` Android desugaring** lives in
  `android/app/build.gradle`, not pubspec — untouched, so no gradle changes.
  Confirm both apps still build after the pubspec dep removal (the transitive
  dep comes back via `packages/push`).
- **Low value, low urgency** — no behaviour change beyond the `_tokenOrNull`
  hardening. Best folded into a session where push is being touched anyway;
  standalone it's ~1 session for cleanliness.

## References

- `planning/features/25-driver-push-notifications/PLAN.md` §A1 — the
  copy-vs-extract decision this reverses
- `packages/maps` / `planning/features/24-driver-app-shell` Stage E — the
  extraction precedent
- `mobile/melos.yaml` — `packages/**` glob (no workspace wiring needed)
