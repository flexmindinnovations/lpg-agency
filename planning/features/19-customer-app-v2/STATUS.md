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

## Outstanding

- **iOS** — `GoogleService-Info.plist` + APNs auth key not set up.
- Test coverage still thin on feature screens — `kyc_screen` and
  `payment_methods_screen` have widget tests; orders / invoices / complaints
  / addresses do not.
- `booking_confirmed` fires on staff *confirm* (`booked → confirmed`), not
  customer placement — so a customer only gets that push once the agency
  confirms the order. Working as designed; noted so it isn't mistaken for
  a bug.

## Issues

None open.
