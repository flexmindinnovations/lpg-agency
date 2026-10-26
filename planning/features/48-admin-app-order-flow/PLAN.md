# 48 — Admin App order flow — Plan

## Problem

Reported 2026-10-26: in the Admin App an order could be booked but never
progressed. The order page only offered Cancel; there was no way to confirm,
pick a driver, load the van, send it out or record the delivery. Live updates
and notifications did not show, and status chips were upper case.

## Changes

Follows the web dashboard's order page and ADR-056 (trip sheet). No backend
change and no migration.

- **Order page:** progress timeline, next-step banner, failed-delivery reason
  and pending-cancellation banners. Actions by status: Confirm, Send out,
  Mark as out for delivery, Record delivery, Delivery failed, Reschedule, Close,
  Cancel / Request cancellation, Approve / Reject a waiting cancellation.
- **Send out sheet:** new trip (free driver and van of the order's branch) or
  an open trip, plus the godown; shows the cylinders against van and godown
  stock; plans the trip and calls `POST /routes/{id}/load-and-dispatch`. A retry
  after a failed load joins the trip it planned.
- **Record delivery sheet:** delivery code (with "Send a new code"), delivered
  and empties per line, payment method and amount. GPS is the order's own
  delivery point (the office is not at the door).
- **Orders list:** the filter chips matched statuses that do not exist
  (`PENDING`), so nothing ever matched. Now All / Booked / Confirmed / On a
  trip / Out for delivery / Failed / Delivered / Cancelled.
- **Realtime:** `RealtimeClient.subscribeToStaffUpdates()` (`orders` +
  `notifications` intents on `/api/v1/ws`). The shell refreshes order screens
  on `order.status_changed`, shows a toast with a View action on
  `notification.new`, and keeps the new Alerts tab badge current.
- **Chips:** `LpgFormat.statusLabel` is sentence case in all three apps.
- **api_client:** `OrderApi` confirm / reschedule / close / approve / reject
  cancellation; `RouteApi` plan / load-and-dispatch / branch filter;
  `FleetApi` (drivers, vans, godowns, filled stock). The unused, wrong
  `AdminApi.reviewCancellationRequest` (`/cancel/review`) was removed.
- **CI:** `admin_app` joins the Mobile CI matrix (format, analyze, test).

## Not in scope

- Push (FCM) for the Admin App: it needs a `google-services.json` for the
  admin app id from the Firebase console. Until then alerts arrive only while
  the app is open (over `/ws`).
- Load-out weighment and extra load lines (web dashboard only).
