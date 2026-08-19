# Phase 11: Order Management Tasks

> Backfilled 2026-08-19 (R8) — the feature shipped, fully tested, with a
> working frontend, but this file was never created. The checklist below
> reflects what was actually built, reconstructed from the code, the
> existing tests, and `planning/MODULE_STATUS.md`'s fix history.

- [x] 1. Implement Domain Layer (`backend/src/lpg/domain/order/order.py`) — `Order` aggregate, 10-state `_TRANSITIONS` graph, `OrderLine`, `DeliveryAddress`, 6 domain events, 2 domain errors
- [x] 2. Implement Application Layer Use Cases (13 use cases: create/confirm/assign/dispatch/depart/deliver/fail-delivery/reschedule/cancel/approve-cancellation/bulk-cancel/close, plus list/get/history reads with pre-query row-scoping)
- [x] 3. Implement `CylinderCapPolicy`/`CreditLimitEvaluator` ports with permissive stub adapters (`infrastructure/order/policies.py`) — real adapters deliberately deferred to Cylinder Ledger (13) / Accounting (14)
- [x] 4. Implement Infrastructure Layer (`SqlAlchemyOrderRepository`, `models/order.py`)
- [x] 5. Generate Alembic migration (`7c3f1a9e2b4d`) — `orders` schema (6 tables), RLS, 4 new permission codes + role grants, backfilled `orders:read`/`orders:cancel` grants `fa52b77ec442` had left empty
- [x] 6. Implement API Layer (`routers/order.py`) — 16 endpoints, row-scoped reads, `Idempotency-Key` on create/deliver, live-checked `orders:cancel_approve`
- [x] 7. Implement Frontend (`@lpg/order/feature-orders` — Order Queue, Order Detail with inline action drawers, customer autocomplete)
- [x] 8. Wire `/orders` route into dashboard `app.routes.ts` (`orders:read` guard)
- [x] 9. Backend tests: domain (`test_domain_order.py`), use cases (`test_order_use_cases.py`), integration smoke (`test_order_endpoints_smoke.py`, full lifecycle + failed-delivery/reschedule + both cancel paths), RBAC (`test_order_rbac.py`, including the live-check case)
- [x] 10. Live browser verification + full frontend gate
- [x] 11. (Phase 11→12 renumbering debt) `route_stop_id` migration debt closed by `de56730bb88f` — the interim `driver_id`/`vehicle_id` columns this migration's own docstring once planned around were dropped once Route/RouteStop existed; current code has no trace of them
- [x] 12. (R1, 2026-08-18) Fix: Create Order drawer's address dropdown used `optionLabel="address_line"` against a response shape that only has `line_1` — every option rendered blank
- [x] 13. (R11, 2026-08-18) Fix (cross-cutting, not order-specific, but first surfaced by order-transition integration tests): `get_unit_of_work`'s catch-all was downgrading every `DomainError` — including `InvalidOrderStatusTransitionError` — to a generic 500 instead of the documented 409
- [x] 14. (R8, 2026-08-19) Backfill this planning directory
