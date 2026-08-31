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

## Outstanding

- **Live end-to-end verification** — the Android build requires
  `android/app/google-services.json` (see `mobile/apps/customer_app/README.md`);
  until it's added the app can't be run on a device/emulator, so the newest
  changes (edge-to-edge nav, payments screen, push) are verified only by
  `flutter analyze` + widget tests.
- The `device_token` migration (`f3a9c1e07b42`) hasn't been applied to a
  live database yet.
- Test coverage is still thin on the feature screens — `kyc_screen` and
  `payment_methods_screen` have widget tests; orders / invoices / complaints
  / addresses do not.
- FCM service-account key (`LPG_FCM_CREDENTIALS_JSON`) not configured, so
  the backend uses `StubPushChannel` (logs, sends nothing).

## Issues

None open.
