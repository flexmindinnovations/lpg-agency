# Status: Customer App V2

**Phase:** 19
**Status:** In Progress — feature-complete against the plan, pending live verification

## Completed Work

All 11 TASKS.md items are implemented and pass `flutter analyze` + the
package's widget tests:

- `StatefulShellRoute` app shell, 4 tabs (Dashboard / Orders / Support /
  Profile); bottom nav is a flush edge-to-edge bar
- Dashboard with notifications bell + `notifications_screen` inbox
- Orders list, `order_detail`, `order_tracking` (map placeholder +
  milestone timeline), `order_placement` bottom-sheet flow
- Invoice list + detail (`invoice_list_screen`, `invoice_detail_screen`)
- Support: ticket list, `raise_complaint`, `complaint_detail`
- Profile: edit profile, address list + add/edit + set-primary, KYC status
- **KYC document list + submission flow** (`kyc_screen`, `submit_kyc_screen`)
  — camera/gallery capture, pre-upload, best-effort OCR auto-fill. Exceeds
  the plan (which only asked to *view* KYC details)
- **Payment Methods screen** (`payment_methods_screen`) — deliberate UI
  placeholder; no gateway integration, per the plan
- Live updates: WebSocket `notification.new` subscription (foreground)
- **Push notifications (FCM)**: backend device-token API + push channel
  (commit `4bbe6d6`), client `PushNotificationService` (commit `0de0dee`)
  — permission, token registration, foreground display, tap deep-linking

## Verified live end-to-end (2026-08-31, Android emulator)

Firebase project `lpg-erp-2b143`, service-account key via
`LPG_FCM_CREDENTIALS_PATH`:

- Launch → permission prompt → FCM token → `POST /notifications/devices`
  → row in `notification.device_token`
- `send_notification` job → real FCM v1 API (`200 OK`) → **notification
  shown on device** with correct title/body (`booking_confirmed`,
  `delivery_confirmed`, `out_for_delivery` all tested)
- **Notification tap → deep-links to Order Details** for the right order
- Edge-to-edge bottom nav bar; Payment Methods screen (empty state +
  coming-soon sheets)
- `device_token` migration `f3a9c1e07b42` applied to local dev DB

## Staff new-order alerts + realtime pipeline (2026-08-31)

A customer / phone / walk-in / whatsapp / api order now raises an
`order_placed_staff` in-app notification to every active
agency_admin / manager / dispatcher (tenant-wide). Staff-created orders
(`booking_source='staff'`) are skipped.

Commits `d0cf9bf` + `936e22c` + `051a3c2`. Four pre-existing bugs fixed to
make the full flow actually work:

- `_STAFF_ALERT_ROLES` used `branch_manager` (never a real role string), so
  even `delivery_failed_staff` never reached managers.
- `EmployeeBranchStaffResolver` needs an employee↔identity phone link the
  demo seed never creates — `order_placed_staff` resolves off
  `identity_user.role` instead.
- **`SqlAlchemyOrderRepository.save()` never called `register_aggregate()`**
  — so a brand-new order's `BookingCreated` was *never dispatched*. No
  handler (notification or realtime) ran on customer order placement.
  `register_aggregate` is now idempotent by identity.
- **The ARQ worker built its UoW with no `event_dispatcher`** — an
  `InAppNotification` created in a job never emitted `notification.new`, so
  the unread badge only updated on its poll. Worker now wires a dispatcher
  + realtime publisher.

## Dashboard realtime fixes (2026-08-31, commits 2d0fee9 + 2e06f15)

- **Notification drawer** now reloads every time it opens —
  `NotificationDrawer.visible` is a `model()` signal, so its `effect()`
  re-runs (was a plain `@Input`, fetched once at construction while
  closed).
- **Order Queue** live-refreshes on `order.status_changed` — new
  tenant-wide `orders` WS channel + intent (`orders:read`-gated), silent
  debounced refetch.

**Full flow verified live end-to-end (2026-08-31):** customer places order
in the emulator → `BookingCreated` dispatched → 3 staff get "New Order" →
dashboard **Order Queue 55→56** and **bell 1→2**, both live over the
WebSocket with no reload; drawer opens and shows the notifications.

## Order-placed acknowledgement + tracking map + live driver tracking (2026-09-01)

Four follow-ups from the previous "Outstanding" list, built and unit/widget
tested (live emulator walkthrough — Stage D below — still pending):

- **`order_placed` customer notification** (commit `114fcc3`) — `BookingCreated`
  now also enqueues a customer-facing "Order Received" push + in-app for every
  non-staff source, so the customer hears back at placement rather than only on
  agency confirm.
- **Feature-screen widget tests** (commit `3ae3adf`) — orders list/detail,
  invoice list/detail, support list + complaint detail, raise-complaint,
  profile, edit-profile. Customer-app suite 10 → 46.
- **Real order-tracking map** (commit `d63eaca`) — `flutter_map` (OpenStreetMap,
  no API key). Destination from the saved address pin, else a Nominatim geocode
  of the address text. New map-pin picker on the add/edit address forms
  (`geolocator` "use my location").
- **Live driver tracking** (commits `e0b56a6` backend, `da5d422` customer,
  `c7a8b2d` driver):
  - `POST /routes/{id}/location` (`routes:deliver`, `in_progress` only) —
    transient telemetry: Redis last-known (120s TTL) + `driver.location` fan-out
    on each per-order channel. `GET /orders/{id}/tracking` read model.
    `GET /routes/active` resolves the caller's route from the token.
  - Driver App's **first business feature**: `ActiveDeliveryScreen` + a
    foreground `LocationSharingController` (geolocator, throttled 1 POST/15s).
  - Customer tracking map shows an animated driver marker seeded from the
    last-known position, "waiting → en route → paused" status.
  - Driver-app Android `compileSdk` → 37, `kotlin.incremental=false` (matches
    customer app). Debug APKs for both apps build clean.

## Stage D — backend E2E verified (2026-09-01)

Ran against the live server + ARQ worker + Redis with real seeded data
(`seed_e2e_customer.py` / `seed_e2e_driver.py`):

- Customer `POST /orders` → the running worker creates an **"Order Received"**
  in-app notification with `reference_type=order` (deep-links to the order).
- `GET /orders/{id}/tracking` → destination coords (from the order's pinned
  `delivery_address`), `route_status`, and `driver_location`.
- `GET /routes/active` → the driver's own route, resolved from the token.
- `POST /routes/{id}/location`: driver on an `in_progress` route → **204**;
  dispatcher → **403**; route not `in_progress` → **409**.
- Redis `tenant:*:route:{id}:driver_pos` last-known key written (120s TTL).
- One ping → **one `driver.location` message per order on the route**, on
  `tenant:{t}:order:{order_id}` (the channel the customer app subscribes to).
- `tracking.driver_location` reflects the last ping.

Verification script: `scripts`-adjacent, kept in the session scratchpad.

## Stage D — emulator walkthrough verified (2026-09-01)

Fresh Pixel emulator, customer app rebuilt from `main`
(`--dart-define=API_BASE_URL=http://10.0.2.2:8000`), signed in as
`e2e.customer@example.com`:

- **"Order Received"** notification appears in the notifications list after an
  order is placed (Stage A).
- **Track Order** renders a real OpenStreetMap map with the delivery-address
  pin + the milestone timeline (Stage B). Order + Tracking ID rows copy on tap.
- Driver pings → the customer map shows the **blue driver marker** and a
  **"Driver en route"** chip, and the marker moves between pings (Stage C3).
  Full path exercised: driver POST → Redis publish → `RedisSubscriber` →
  WebSocket → `driverLocationProvider` → map marker.
- Driver row + details sheet (name, vehicle, tap-to-copy / **Call**).

**Driver app, same emulator** (`e2e.driver@example.com`, OTP sign-in):
`ActiveDeliveryScreen` shows the IN PROGRESS route + stops; flipping **"Share
live location"** triggers the geolocator permission flow and then
`POST /routes/{id}/location → 204` from the real app (`user_id` = the e2e
driver), with the card updating to "Customers can see your location.". Both
apps' halves of the live-tracking loop verified on-device.

`seed_e2e_driver.py` now sets the identity-user phone number so the Driver
App's phone-OTP sign-in works with the seeded account.

## Outstanding

- Re-verify invoices / support / profile / address CRUD screens on-device
  post-rebuild (widget tests pass; not walked through the emulator).
- iOS Firebase (`GoogleService-Info.plist` + APNs key).
- Driver app only *views* a route + shares location — the delivery workflow
  (mark departed, record delivery + proof-of-delivery, collect payment) still
  lives only in the dashboard/API.
- **iOS** — `GoogleService-Info.plist` + APNs auth key not set up.
- **Driver-app background location** — DONE (commit `f57658e`): geolocator
  runs an Android foreground service / iOS background updates, so sharing
  continues when the Active Delivery screen closes or the app is backgrounded.
- **LocationIQ maps (Step E) — DONE.** Both the geocoder *and* the map tiles
  now use [LocationIQ](https://locationiq.com) (hosted, higher-limit, keyed
  with the same `LOCATIONIQ_API_KEY`), with OSM/Nominatim as the no-key
  fallback:
  - `GeocodingService` → LocationIQ forward-geocoding (Nominatim-compatible),
    else raw Nominatim.
  - `LocationMap` `TileLayer` → LocationIQ `light` basemap (clean greyscale so
    the pin/route pop), else the raw OSM tile CDN. The "Made with flutter_map"
    promo is turned off (`showFlutterMapAttribution: false`); a minimal
    `© OpenStreetMap · © LocationIQ` legal attribution stays.
  - Key passed via `--dart-define-from-file=dart_defines.local.json`
    (gitignored; see `dart_defines.local.json.example`) — never committed.
  - 5 geocoding + 5 map-widget unit tests cover the keyed vs fallback paths.

## Issues

None open.
