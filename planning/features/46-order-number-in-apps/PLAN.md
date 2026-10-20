# 46 — Same order number in the apps as on the dashboard — Plan

**Problem.** The Customer App showed orders as `Order #4C6826F9` (a UUID
prefix) and the Driver App's stop list did the same, while the dashboard,
invoices and notifications use the order number (`ORD000027`). Customers and
drivers quoted a reference the office could not find.

**Change.**
- Backend: `RouteStopResponse` gains `order_number` (read with the stops in
  `SqlAlchemyRouteRepository`, carried on `RouteStop` for display only), so the
  Driver App's route list has it without a per-stop order fetch.
- Mobile: `LpgFormat.orderNumber(orderNumber, id)` is the single place an order
  is labelled; it falls back to `#` + short id only when a number is missing.
  Used by the customer order list, detail, dashboard banner, complaint picker,
  tracking, and by the driver Today card, stop tiles and stop detail.
- The tracking screen's separate "Tracking ID" (UUID prefix) is unchanged.

No migration. No API break (new optional field).
