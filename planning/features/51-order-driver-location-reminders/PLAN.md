# 51 - Driver, vehicle, live location and reminders on the order page

Dashboard order page (`/orders/:id`):

- **Driver and vehicle card** from `GET /orders/{id}/tracking` (already used by the
  Customer App). Shows driver name and phone, van registration and model, trip status,
  and "Open trip" (`/dispatch?trip=<route id>`, new). `OrderTrackingResponse` gained `route_id`.
- **Live location** while the order is out for delivery: the Driver App already sends
  pings (`POST /routes/{id}/location`) to a 2-minute Redis cache. The page re-reads
  tracking every 15 s and shows an OpenStreetMap embed (no key), "updated N minutes
  ago", and an Open in Maps link. A warning shows when the last ping is over 2 minutes old.
- **Remind customer** (`orders:dispatch`): `POST /orders/{id}/reminders` with a preset
  (delivery today, on the way, keep empty ready, payment due) or custom text (max 300).
  Delivered as in-app + push (`order_reminder` notification type). No SMS/WhatsApp:
  DLT templates cannot carry free text. Limits: 2 minutes between reminders, 5 per
  order per day (429). Each send is stored in `orders.order_reminder` and appears in the timeline.
  Refused for finished orders and for customers with no app login (409).

Not done: the admin mobile app order page does not have these yet.

## Remind driver (added 2026-10-30)

- `POST /orders/{id}/reminders` takes `audience` (`customer` default, or `driver`). Driver
  presets: start the trip, please hurry, turn on live location, call the office, plus custom.
  Delivered to the driver of the order's trip as `order_reminder_driver` (in-app + push).
- Stored in the same table; driver reminders use a `driver_` preset key (no migration).
  The 2-minute gap and 5-per-day limits count per audience.
- 409 when the order is finished, is not on a trip yet, or the driver has no Driver App login.
- Order page: "Remind driver" button next to "Remind customer" once a driver is assigned;
  the timeline says who got each reminder.
