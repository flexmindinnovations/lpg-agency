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

## Staff new-order alerts (2026-08-31, commits d0cf9bf + 936e22c)

A customer / phone / walk-in / whatsapp / api order now raises an
`order_placed_staff` in-app notification to every active
agency_admin / manager / dispatcher (tenant-wide). Staff-created orders
(`booking_source='staff'`) are skipped. **Verified live in the dashboard**
— bell count + Notifications page both show "New Order". Fixed a
pre-existing bug: `_STAFF_ALERT_ROLES` used `branch_manager` (never a real
role), so `delivery_failed_staff` never reached managers either.

## Dashboard realtime fixes (2026-08-31, commits 2d0fee9 + 2e06f15)

- **Notification drawer** now reloads every time it opens —
  `NotificationDrawer.visible` is a `model()` signal, so its `effect()`
  re-runs (was a plain `@Input`, fetched once at construction while
  closed). Verified: drawer shows the staff new-order notifications.
- **Order Queue** live-refreshes on `order.status_changed` — new
  tenant-wide `orders` WS channel + intent (`orders:read`-gated), silent
  debounced refetch. Verified: count 52 → 53 on a new booking, no reload.

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
