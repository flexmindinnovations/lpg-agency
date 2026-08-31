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

## Verified live (2026-08-31, Android emulator)

- App builds + runs against Firebase project `lpg-erp-2b143`
- Notification permission prompt → FCM token → `POST /notifications/devices`
  → row in `notification.device_token`
- Edge-to-edge bottom nav bar; Payment Methods screen (empty state +
  coming-soon sheets)
- `device_token` migration `f3a9c1e07b42` applied to local dev DB

## Outstanding

- **Real push delivery untested** — `LPG_FCM_CREDENTIALS_JSON` not set, so
  the backend still uses `StubPushChannel` (logs, sends nothing). Need the
  service-account key to test an actual tray notification + tap deep-link.
- **iOS** — `GoogleService-Info.plist` + APNs auth key not set up.
- Test coverage still thin on feature screens — `kyc_screen` and
  `payment_methods_screen` have widget tests; orders / invoices / complaints
  / addresses do not.

## Issues

None open.
