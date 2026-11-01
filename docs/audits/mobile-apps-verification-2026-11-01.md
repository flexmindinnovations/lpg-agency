# Mobile apps verification, 2026-11-01

Scope: customer, driver and admin apps against the backend on `main` (after #107). Checked by reading code, Flutter unit and widget tests for all three apps, and the backend order, payment, invoice, complaint and notification suites against a local Postgres 16, Redis and moto stack. **No emulator or physical device was available, so push delivery, taps from the tray and the Razorpay checkout were not exercised on a phone.**

## Issues found and fixed in this change

| # | Issue | Fix |
|---|---|---|
| 1 | A push tapped while the app was cold-starting, or while signed out, was lost: the router redirects everything to splash/login until the session is `authenticated`, and nothing remembered the route. | New `DeepLinkGate` (packages/auth) holds the tapped route and opens it once the session is signed in. Used by all three apps. Unit tested. |
| 2 | Customer push for a complaint or a refill reminder opened the inbox; admin pushes for complaints, trips, cash handovers, stock, compliance and pricing all opened Alerts. | One route mapping per app (`customerRouteFromData`, `adminRouteFromData`, `driverRouteFromData`) now covers every reference type the backend sends. Tested. |
| 3 | Tapping an item in the in-app inbox went somewhere different from tapping the same push (customer: orders only; admin: orders only). | The inbox now uses the same mapping as the push. |
| 4 | Customer order screen kept its payment state after a payment or live update: the order-payments, cancellation and history providers were not refreshed, so "Pay Online" could stay after the order was paid. Invoice detail and complaint screens were not refreshed by live events at all. | Live events now invalidate order payments, cancellation, history, invoice detail, invoice list, and complaint list/detail. Resume-from-background also refreshes complaints. |
| 5 | Customer app offered Pay Online / UPI QR on orders that are billed to a credit account. | Pay is not offered for `credit` orders before delivery; a "Billed to your credit account" note shows instead. |
| 6 | Customer app showed "Cancel Order" once the driver was on the way, but the server only accepts a request the agency must approve. | The button reads "Request Cancellation" for `out_for_delivery`. Rules now live in one place (`OrderPresentation.canCancel`, `canPrepay`) and mirror the backend state machine. |
| 7 | Driver app: a double tap on "Start this delivery" or "Delivery failed" could queue the action twice. | In-flight guard in the stop screen. |

## Verified (tests that pass)

- Cancellation is enforced by the server: a delivered, closed, cancelled or draft order cannot be cancelled (unit test for each status, plus an HTTP test that a delivered order returns 409 `INVALID_STATE_TRANSITION`). Post-dispatch cancel creates an approval request instead.
- Online payment is refused when nothing is due (existing test `nothing_due`, 409), and the server only accepts prepayment in confirmed, assigned, ready, out-for-delivery and failed-delivery states, or against an issued/partially paid invoice.
- Backend: 74 integration tests (order lifecycle incl. dispatch, delivery, failed delivery, reschedule, cancel and approval; online payments; invoices; complaints; in-app notifications; order RBAC) pass locally. Unit tests for the order use cases pass.
- Flutter: customer, driver, admin app tests and the auth package tests pass; `flutter analyze` is clean.

## Not fixed / not verified

- Real-device behaviour: FCM delivery, tapping a tray notification in background/terminated state, the Razorpay sheet, offline sync on the driver app. The route logic is unit tested, the plumbing is not.
- The customer app's `failed_delivery` order shows neither Cancel nor Pay (backend would allow a cancellation request). Left as is: the banner tells the customer the agency will arrange another delivery.
- The customer order screen does not know whether the driver has already collected cash for an order that is still `out_for_delivery`. The driver records delivery and payment together, so the order becomes `delivered` at that moment; until the driver's offline queue syncs, the customer still sees the previous status. A server-side "payment status" field on the order would remove the guesswork; it is not added here because the driver delivery/payment flow is being rebuilt in another thread.
- Loaders: the pairs of buttons reviewed (admin KYC review, trip, settle, stock, driver/vehicle sheets, customer pay section, driver stop and delivery) disable the other buttons while one runs and only spin the pressed one. I did not find another screen where one tap spins several buttons after #107; this was checked by code reading, not on a device.
- Admin app realtime refreshes orders and alerts only (staff feed); other admin lists refresh on pull or resume.
