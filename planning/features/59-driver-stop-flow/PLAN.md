# 59 - Driver stop flow: deliver, pay, complete (ADR-069)

Backend (PR 1): payment must be settled before an order is completed, replay-safe `/deliver`, `GET /orders/{id}/settlement`, spend capped at balance due.
Driver app (PR 2): three-step stop screen (Cylinders, Payment, Confirm), paid-online banner, one idempotency key per submission, navigation reset after completion.
Out of scope: end-of-day cash handover and admin reconciliation (unchanged).
