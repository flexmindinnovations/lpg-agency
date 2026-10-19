# 44 — Book only orderable cylinders — Tasks

- [x] Server: orderable list + guard on create and confirm
- [x] Endpoint `GET /orders/orderable-cylinder-types`
- [x] WhatsApp assistant uses the same rule
- [x] Dashboard booking form uses the list
- [x] Customer App order screen uses the list (needs a new APK)
- [x] Unit and integration tests
- [x] Concurrency: bookings and confirmations at one branch take a
      transaction-scoped PostgreSQL advisory lock before the stock check, so
      two can't both claim the last cylinders (before the fix, four
      simultaneous 150-cylinder bookings against 200 in stock all succeeded).
