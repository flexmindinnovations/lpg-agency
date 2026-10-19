# 41 — Live order updates and notifications — Plan

## Problem

Reported 2026-10-19: order status changes (e.g. ORD000022 going Out For
Delivery) didn't show in the dashboard or the apps until a manual refresh, and
nothing raised a notification.

The realtime stack (`/api/v1/ws`, Redis Pub/Sub, `realtime_handlers.py`) and
the clients' WebSocket wiring already existed. The gaps:

- `dispatch()`, `depart()` and `reschedule()` record no domain event, so
  `ready_for_dispatch`, `out_for_delivery` and the reschedule were never
  published. The other transitions published a status derived from the event
  class name (`"created"`, `"inventoryreserved"`), not the real status.
- The customer "out for delivery" notification was never enqueued (a TODO).
- Staff got no bell entry when a driver started a route or delivered.
- The dashboard order detail page didn't listen at all; the bell bumped its
  badge but showed nothing.
- The dashboard socket reconnected with the token it first opened with; once
  that expired (15 minutes) the server closed with 1008 and the client gave up.
- `ConnectionManager.connect()` re-registered a socket on every subscribe
  message, replacing its channel set and orphaning a sender loop.
- The driver app had no WebSocket; a push only refreshed the Alerts badge.

## Changes

- **Domain:** new `OrderStatusChanged` (order id/number, customer, from/to
  status, changed_by) recorded by every transition. `InAppNotificationCreated`
  now carries body and reference.
- **Realtime:** `order.status_changed` is published from `OrderStatusChanged`
  with the real status; `notification.new` carries title, body and reference.
  A socket's later subscribe messages add channels instead of re-registering.
- **Notifications:** `out_for_delivery` (customer push/SMS) on depart;
  `route_started_staff` on route `-> in_progress`; `order_delivered_staff` on
  delivery. Order bodies use the order number instead of a UUID prefix.
- **Dashboard:** order detail refreshes on the orders feed and toasts changes
  made by someone else; the bell toasts every new notification; the socket
  reconnects with the current token and refreshes it on 1008.
- **Customer app:** an order notification refreshes the order lists and the
  order's detail.
- **Driver app:** connects to `/ws`; a notification or push refreshes the
  badge, inbox and active route.

No reverse-proxy change: Caddy's `reverse_proxy` upgrades WebSockets on
`/api/*` by default.
