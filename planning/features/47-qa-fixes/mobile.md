# 47 QA fixes: mobile (customer app, driver app, shared packages)

Source: `mobile-findings.md` (QA pass, 31 findings: customer CA-01..18, driver DR-01..13).
Branch worktree: `wt/mobile`. No migrations. API changes listed below; the client is regenerated in separate `chore(api)` commits.

## Findings → change → verification

| ID | What changed | Files (main) | Verified by |
|---|---|---|---|
| CA-01 | Log Out asks first, then always signs out: the FCM token read is guarded, and logout runs in `finally`. | customer `profile_screen.dart`, `push_notification_service.dart` | Customer profile widget test (RecordingAuthRepository) |
| CA-02 | **Not changed here.** Phone sign-in normalisation belongs to the "+91" thread. My commit 42171a7 was reverted in 942b329. | — | — |
| CA-04 | The customer sees their delivery code on Order detail and Track Order. The new `GET /orders/{id}/delivery-code` is customer-only (staff get 403) and ownership-checked (another customer gets 404). It returns null unless the order is out for delivery. The code is kept in Redis next to the hashed OTP. | backend `application/order/{ports,use_cases}.py`, `infrastructure/order/delivery_code_store.py`, `routers/order.py`; app `delivery_code_card.dart` | Unit `TestGetDeliveryCodeUseCase`; integration `TestCustomerDeliveryCode`; widget tests (order detail, tracking) |
| CA-06 | Booking shows a summary (qty × name, unit price, total) above Place Order. Order lines name the cylinder. Total shows "Estimated total" from list prices, or "Not charged" for cancelled orders. | `order_placement_screen.dart`, `order_detail_screen.dart`, `order_presentation.dart` | `order_placement_screen_test`, `order_detail_screen_test` |
| CA-07 | While a cancellation request is pending, a banner is shown and Cancel and Pay Online are hidden. | `order_detail_screen.dart`, `orders_provider.dart` (`pendingCancellationProvider`) | Widget test |
| CA-08 | An agency-verified account with no uploads says "KYC verified", not "nothing submitted". A missing email reads "Not added". | `kyc_screen.dart`, `profile_screen.dart` | `kyc_screen_test` |
| CA-09 | Ticket rows read "Late Delivery · CMP000007". Shared category/status labels. | `support_screen.dart`, `complaint_presentation.dart`, `complaint_detail_screen.dart` | `support_screen_test` |
| CA-10 | New backend category `GasLeakSafety`, always Critical. New `GET /support/contacts` (helpline from tenant config `emergency_helpline_number`, default 1906; agency `customer_support_phone`). Support leads with a "Smell gas?" card that has Call 1906 / Call your agency, and falls back to 1906 offline. Choosing the gas-leak category shows the same card. Customers can no longer pick Critical. | backend `domain/complaint`, `routers/support.py`, `application/tenant/tenant_configuration.py`; app `emergency_contacts_card.dart`, `raise_complaint_screen.dart`; dashboard `feature-complaints.ts` option | Unit test (Critical forced); `test_support_contacts_smoke.py` (3); support / raise widget tests; api_client test |
| CA-11 | An empty cancellation reason shows an inline error in the dialog. | `order_detail_screen.dart` | Widget test |
| CA-12 | LpgTextField / LpgDropdownField expose `label` (plus ", required") as the field's semantics name. | design_system `lpg_text_field.dart`, `lpg_dropdown_field.dart` | `components_test.dart` (isSemantics) |
| CA-13 / DR-12 | `LpgAdaptiveShell`: bottom bar below 600 px; above it, a NavigationRail with a 720 px content cap. Login is capped at 480 px. | design_system `lpg_adaptive_shell.dart`, `layout.dart`; both `app_shell.dart` + routers | design_system tests; driver rail test at 820 px |
| CA-14 | Section header action is centred. The dropdown selected item ellipsises. Choice chips use padded (48 px) tap targets. | design_system | components tests |
| CA-15 (app) | The invoice names GST and shows GST per line as returned. A test proves the whole card is tappable. Delivered orders get View Invoice and Order Again. | `invoice_detail_screen.dart`, `order_detail_screen.dart` | invoice list / detail tests |
| CA-16 | Removed the UUID "Tracking ID". "1 cylinder type" is singular. Branding is "LPG Agency". City, State and a 6-digit pincode are required. Payment Methods explains the ways to pay (no "Add card"). | `order_tracking_screen.dart`, `dashboard_screen.dart`, `address_form_fields.dart`, `payment_methods_screen.dart` | `address_form_fields_test`, `payment_methods_screen_test`, `widget_test` |
| CA-17 | New `GET /online-payments/availability`. Pay Online is hidden when the gateway isn't configured. A start error is shown inline, and SERVICE_UNAVAILABLE re-checks availability. | backend `routers/online_payment.py`; app `pay_online_section.dart`, `order_payments_provider.dart` | Integration `TestOnlinePaymentAvailability`; api_client test |
| DR-01 / DR-10 | The cash reminder covers every completed route with an undeclared handover, and never shows for ₹0 with no cash stops. | driver `cash_handover_provider.dart`, `today_screen.dart`, `deliveries_screen.dart` | `pending_cash_handovers_test.dart` |
| DR-02 | The delivery error shows in a banner directly above Confirm, scrolled into view, with a heavy haptic and a toast. | `record_delivery_screen.dart` | Widget test (banner position) |
| DR-03 | "Check again" invalidates both the route and the order, so one tap shows Start. | `stop_detail_screen.dart` | Widget test |
| DR-05 | `GET /routes/active` prefers in_progress, then loaded, then planned (newest first within each), so a newer planned route never hides the trip in hand. | backend `persistence/repositories/route.py` | Integration `TestActiveRoutePrefersTheOneOnTheRoad` (fails without the fix) |
| DR-06 | The stop shows the customer's name and phone with a Call button (`GET /customers/{id}`; drivers hold `customers:read`; cached offline). An unpinned stop offers "Navigate by address". | `stop_customer_provider.dart`, `stop_detail_screen.dart`, `stop_map_card.dart` | stop detail / map card tests |
| DR-07 | `DriverGeolocator.deliveryFix()`: checks the location service, asks for permission, 20 s timeout. Each failure gives a retryable message. **GPS stays mandatory** (BR-08/BR-23). | `location_sharing.dart`, `record_delivery_screen.dart` | Widget test (denied); unit test (timeout) |
| DR-08 | Cash handover and Van load are top-level routes above the tabs, so the Deliveries tab no longer reopens them. | driver `router.dart`, `today_screen.dart`, `deliveries_screen.dart` | app_shell / widget tests |
| DR-09 | Backend: optional `note` (≤500) on failed delivery; history reads "Label — note". App: the sheet has a Note field, and a failed or finished stop no longer says "Collect ₹". The customer order detail shows the failure reason. | backend `domain/order/order.py`, router; driver `failed_delivery_sheet.dart`, `delivery_mutations.dart` | Domain unit tests; integration (run on own DB); stop detail tests |
| DR-11 | Log Out confirm (both apps). DAC / code fields have real labels, so the hint isn't truncated. The route card shows the date and van registration. The signature pad keeps owning vertical drags by design (it must, to draw), and the pad is short. | `profile_screen.dart`, `record_delivery_screen.dart`, `today_screen.dart` | today / profile tests |

## Deferred / not mine

- **CA-02:** handled by the "+91" thread. My change was reverted.
- **CA-03:** backend message, auth engineer.
- **CA-05:** in-app notification data, realtime engineer. The bell already shows an unread badge once rows exist.
- **CA-18:** realtime engineer.
- **DR-04:** manifest backend, inventory engineer. The app still reads `loaded_lines`.
- **DR-13:** inventory engineer.
- **CA-15:** invoice PDF download / share needs a backend PDF endpoint. Tax ₹0 comes from pricing config (backend / billing).
- **DR-09:** no "Other" reason, because D-12 fixes exactly five codes; the note covers it. Reschedule has no date field because the backend has no reschedule-date API; the driver puts the customer's preferred day in the note.
- **CA-08:** the customer record email differs from the login email; that is a data / backend question.
- **Complaints:** customer follow-up messages on a complaint are a new flow, not built.

## API changes (all additive)

- `GET /api/v1/orders/{order_id}/delivery-code` → `{code} | null` (customer only).
- `POST /api/v1/orders/{id}/failed-delivery`: optional `note` (max 500).
- `GET /api/v1/online-payments/availability` → `{available}` (orders:read).
- `GET /api/v1/support/contacts` → `{emergency_helpline, agency_phone}`. Two new config keys: `emergency_helpline_number` and `customer_support_phone`. New setting `emergency_helpline_number = "1906"`.
- Complaint category `GasLeakSafety`.
- Behaviour change: `GET /routes/active` ordering (DR-05).

## Tests run (final)

- **Flutter:**
  - analyze: clean for design_system, api_client, core, customer_app and driver_app.
  - tests: 43, 67, 3, 65 and 98 respectively, all passing.
- **Backend:**
  - unit: 1234 passed.
  - ruff, mypy and lint-imports: clean.
  - integration on `lpg_test_mobile`: support contacts (3), online payment availability, customer delivery code, and active route ordering, all passing. The failed-delivery note test was run by pointing its fixture at my DB temporarily.
- **Note:** before the lead's test-DB update, `test_order_endpoints_smoke.py` was run once against the shared `lpg_test`.

## For the lead when merging

- Regenerate the API client after merging alongside other branches:
  - `cd backend && uv run python scripts/export_openapi.py`
  - `cd frontend && npm run generate:api-client`
- Likely conflict points:
  - backend `api/app.py` (support router import).
  - `application/order/use_cases.py` (Depart/Resend take a `delivery_code_store`).
  - `domain/order/order.py`.
  - `persistence/repositories/route.py`.
  - Both apps' `app_shell.dart` (now `LpgAdaptiveShell`), which the realtime branch also touched. Keep its 5-line change and the adaptive shell.
  - Both routers.
- No migrations.

## ADR draft

1. **Customer-readable delivery code.** The OTP service keeps only a salted hash. To let the owning customer read the code, departure and resend also write the plaintext to Redis (`tenant:{t}:order-delivery-code:{order}`) with the same TTL. It is readable only through an ownership-checked, customer-only endpoint, and only while the order is out for delivery. Alternative rejected: storing the plaintext in Postgres (it would outlive the OTP and widen exposure).
2. **Safety complaints.** `GasLeakSafety` is a complaint category that the domain always files as Critical, whatever the client sends. Customers can no longer choose Critical themselves.
3. **Support contacts as tenant configuration.** `emergency_helpline_number` defaults to 1906 (the national LPG emergency number), and `customer_support_phone` is optional. Both are served by `GET /support/contacts`. The app hard-codes the 1906 fallback so the helpline shows offline.
4. **Online-payment availability endpoint.** Apps ask the backend whether the gateway is configured, instead of offering Pay Online and failing.
5. **Active route selection.** A driver's "active" route is the one on the road first (in_progress > loaded > planned), not simply the newest.
