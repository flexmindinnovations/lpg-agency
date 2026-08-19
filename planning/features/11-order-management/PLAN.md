# Phase 11: Order Management Implementation Plan

## Goal
Own the full order lifecycle — from a customer booking a cylinder through confirmation, driver/vehicle assignment, dispatch, delivery (with Proof of Delivery), and either close-out or cancellation — as the aggregate everything downstream (Delivery/Route, Cylinder Ledger, Accounting, Notifications) hangs off.

## Scope
1. **Domain Layer**: `Order` aggregate root — a 10-state machine (`draft → booked → confirmed → assigned → ready_for_dispatch → out_for_delivery → {delivered → closed | failed_delivery → ready_for_dispatch}`, plus `cancelled` reachable from every pre-delivery state), `OrderLine` (backorder split, over-delivery guard), a frozen `DeliveryAddress` snapshot taken at booking time.
2. **Application Layer**: one use case per endpoint (create/confirm/assign/dispatch/depart/deliver/fail-delivery/reschedule/cancel/approve-cancellation/bulk-cancel/close), plus `CylinderCapPolicy`/`CreditLimitEvaluator` as ports for BR-04/BR-19.
3. **Infrastructure Layer**: `SqlAlchemyOrderRepository`, `orders` schema (`order`, `order_line`, `order_status_history`, `failed_delivery_record`, `cancellation_record`, `proof_of_delivery`).
4. **API Layer**: 16 endpoints under `/orders`, all claims-based `require_permission` except `POST /orders/{id}/cancel/approve`, which is live-DB-checked (D-19 — a stale/tampered claim must not survive a permission revocation between token issuance and this specific, high-consequence action).
5. **Frontend UI**: `@lpg/order/feature-orders` — Order Queue (list + Create drawer), Order Detail (all action drawers/buttons for the full lifecycle, including a signature-pad + photo + GPS + OTP delivery flow).

## Integration points
- `Order.route_stop_id` is an FK into `delivery.route_stop`, owned by Phase 12 (Route/Dispatch — see `planning/features/12-delivery-dispatch/`, already documented). `assign()` sets it; Order never mutates Route's own state beyond the specific handoff methods Route exposes (`record_proof_of_delivery`, `record_failed_delivery`, `cancel_stop`, `reschedule_stop`, `change_status`).
- `deliver()` fires `CylinderDelivered` — the event Phase 13 (Cylinder Ledger) subscribes to.
- `Idempotency-Key` is required on `POST /orders` and `POST /orders/{id}/deliver` — the offline-first Driver App's retry path depends on both being genuinely idempotent, not just accepted twice.

## Out of Scope
- BR-04 (cylinder cap) / BR-19 (credit limit) enforcement at `confirm()` — the ports exist, but both adapters are still permissive no-op stubs (see STATUS.md; this is a currently-open gap, not a historical one).
- Route/RouteStop domain internals — owned by Phase 12.
