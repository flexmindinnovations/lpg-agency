# Phase 12: Delivery & Dispatch Implementation Plan

Superseded 2026-08-13 by a full completion plan written after an independent audit found the phase's original "COMPLETE" claim false (see `STATUS.md`'s Audit Findings). This file now records what was actually planned and built; the plan itself lives at (session-local) `amber-drifting-lighthouse.md` — its decisions are summarized below since that file is not part of the repository.

## Goal

Make `Route`/`RouteStop` the real dispatcher-facing grouping construct for deliveries, replacing Order Management's interim `driver_id`/`vehicle_id` columns exactly as `7c3f1a9e2b4d_create_orders_schema.py`'s own docstring instructed when those columns were added in Phase 11. Ship a working Dispatch Board.

## Scope decisions

1. **Route/RouteStop becomes real.** `orders.order.driver_id`/`vehicle_id` are dropped; `orders.order.route_stop_id` (FK to `delivery.route_stop`) replaces them. `AssignOrderUseCase` (Order Management's existing single-order "Assign" drawer) now finds-or-creates a single-stop `Route` for the chosen driver/vehicle/date and delegates to `AssignOrderToRouteUseCase` internally — the dispatcher never has to learn two different "assign" flows. The Dispatch Board adds genuine multi-order grouping on top: plan one `Route`, assign several unassigned orders onto it.
2. **`VehicleLoadEvent`/`VehicleShiftReconciliation` descoped** — never built as separate entities. Loading a vehicle reuses Inventory Management's `LoadTransferUseCase` (atomic warehouse→vehicle transfer); reconciling one reuses Inventory's existing `ReconciliationRecord`/approval workflow. See `docs/data/01-domain-model.md` §4.4's divergence note for the full rationale. `Route`'s `Loaded`/`Reconciled` transitions are thin wiring around Inventory's own use cases, not new business logic.
3. **POD/failed-delivery capture stays on Order's existing endpoints.** `POST /orders/{id}/deliver` and `POST /orders/{id}/failed-delivery` (built in Order Management) remain the only driver-facing "record what happened" actions. They additionally sync the paired `RouteStop`'s status (and, when it's the route's last unresolved stop, auto-complete the route) — Route never gets its own competing capture UI.

## What shipped

- **Domain**: `Route.cancel_stop()`, `Route.reschedule_stop()`, `Route._auto_complete_if_all_stops_terminal()` (the `Completed` transition is automatic once every stop is terminal, not a manual action), an empty-route guard on `change_status("completed")`, `Route.record_planned()` extracted from `__init__` (mirrors `Order`'s own never-record-events-in-`__init__` convention). `Order._route_stop_id` replaces `_driver_id`/`_vehicle_id`.
- **Migration** (`de56730bb88f`): CHECK constraints on `route`/`route_stop` status, RLS on `route` (not `route_stop` — child-table precedent, same as `orders.order_line`), audit columns + partial unique index on `route_stop`, indexes, `routes:manage`/`routes:deliver` permissions (`routes:create`/`routes:read` were already seeded with no grants — this migration grants them), `orders.order.route_stop_id` added / `driver_id`+`vehicle_id` dropped.
- **Application**: `AssignOrderToRouteUseCase`, `LoadVehicleForRouteUseCase` (wraps Inventory's transfer logic), `CompleteRouteReconciliationUseCase` (409 `ROUTE_RECONCILIATION_PENDING` if no approved reconciliation exists), all following the atomic multi-aggregate pattern `LoadTransferUseCase` established: mutate everything in memory, save only after every mutation succeeds, commit once.
- **Infrastructure**: `SqlAlchemyRouteRepository` rewritten onto the standard `unit_of_work` constructor + `register_aggregate()` pattern — fixes a real, previously-shipped bug where Route's domain events were silently never dispatched (the old repository wrote events to `session.info`, which `UnitOfWork.commit()` never reads).
- **API**: `POST /routes`, `GET /routes`, `GET /routes/active-for-driver/{id}`, `GET /routes/{id}`, `POST /routes/{id}/assign-order`, `POST /routes/{id}/load`, `POST /routes/{id}/reconcile`, `PATCH /routes/{id}/status`. Role-scoped `routes:read` (driver → own route, dispatcher/manager → branch, else tenant-wide).
- **Frontend**: `@lpg/delivery/feature-dispatch` rebuilt from a list+create stub into a real Dispatch Board — route-status columns, route cards, a Route Detail drawer (Load Vehicle sub-form, Start/Cancel, Reconcile with a 409-aware message linking to Inventory), an unassigned-orders panel with click-to-assign. Fixed the hardcoded-first-branch bug (`branches()[0]`) with a real, required, user-driven branch selector.

## Out of scope (unchanged from the original plan)

- Building the Flutter Driver App (API integration happens from the Flutter side).
- Automated Route Optimization (deferred).
