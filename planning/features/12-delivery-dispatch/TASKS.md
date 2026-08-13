# Phase 12: Delivery & Dispatch Tasks

Rewritten 2026-08-13 to match what was actually built (the original list, reproduced in `STATUS.md`'s history, was 0% checked despite the phase being marked complete — see the Audit Findings).

## 0. Gate fixes (pre-existing breaks found by audit)
- [x] `import-linter`: `lpg.api.v1.dependencies.delivery -> lpg.infrastructure.persistence.repositories.route` added to `ignore_imports`
- [x] `frontend/libs/delivery/feature-dispatch/project.json` Nx tags (`[]` → `["type:feature","scope:delivery"]`)
- [x] `ruff` import-order fix in `api/v1/routers/route.py`

## 1. Domain Layer
- [x] `Route.cancel_stop(stop_id)`, `Route.reschedule_stop(stop_id)`
- [x] `Route._auto_complete_if_all_stops_terminal()` — `Completed` reached automatically, not by manual action
- [x] Empty-route guard on `change_status("completed")`
- [x] `Route.record_planned()` extracted from `__init__` (was auto-firing `RoutePlanned` on every DB reconstruction — real bug, fixed)
- [x] `Order._route_stop_id` replaces `_driver_id`/`_vehicle_id`; `Order.set_route_stop()`
- [x] `VehicleLoadEvent`/`VehicleShiftReconciliation` — deliberately not built (see `PLAN.md` scope decision + `01-domain-model.md` §4.4 divergence note)

## 2. Application Layer
- [x] `AssignOrderToRouteUseCase` (atomic Route+Order+InventoryLocation)
- [x] `LoadVehicleForRouteUseCase` (wraps Inventory's `LoadTransferUseCase` logic)
- [x] `CompleteRouteReconciliationUseCase` (409 `ROUTE_RECONCILIATION_PENDING` gate)
- [x] `PlanRouteUseCase`, `UpdateRouteStatusUseCase` (only `in_progress`/`cancelled` reachable), `GetRouteUseCase`, `ListRoutesUseCase`, `GetActiveRouteForDriverUseCase`
- [x] Order Management's `AssignOrderUseCase`/`DepartOrderUseCase`/`DeliverOrderUseCase`/`RecordFailedDeliveryUseCase`/`RescheduleOrderUseCase`/`CancelOrderUseCase`/`ApproveOrderCancellationUseCase` updated to create/sync the paired `Route`/`RouteStop`
- [x] `RouteRepository` port gains `get_route_with_open_stop_for`, `count_active_routes_for_order`, `get_stop_owner`

## 3. Infrastructure Layer
- [x] `RouteStopModel` audit columns
- [x] `orders.order.route_stop_id` FK; `driver_id`/`vehicle_id` columns dropped
- [x] `SqlAlchemyRouteRepository` rewritten onto `unit_of_work`/`register_aggregate()` (fixes silently-dropped domain events)
- [x] Migration `de56730bb88f`: CHECK constraints, RLS on `route`, audit columns + partial unique index on `route_stop`, indexes, `routes:manage`/`routes:deliver` permissions — applied to Supabase dev

## 4. API Layer
- [x] `api/v1/schemas/route.py`, `api/v1/schemas/order.py` (`route_stop_id` replaces `driver_id`/`vehicle_id`)
- [x] `api/v1/routers/route.py` full endpoint set (plan/list/get/active-for-driver/assign-order/load/reconcile/status)
- [x] `api/v1/routers/order.py` updated for `route_stop_id`-based scoping
- [x] `api/v1/dependencies/delivery.py`, `dependencies/order.py` wiring (including the `TYPE_CHECKING`-import runtime bug found and fixed)

## 5. Backend Tests
- [x] `tests/unit/test_domain_route.py` (80 tests)
- [x] `tests/unit/test_route_use_cases.py` (19 tests, incl. atomic-failure cases)
- [x] `tests/integration/test_route_endpoints_smoke.py` (full lifecycle)
- [x] `tests/integration/test_route_rbac.py` (permission matrix + scoping + cross-tenant RLS)
- [x] `tests/unit/test_domain_order.py`, `test_order_use_cases.py`, `tests/integration/test_order_endpoints_smoke.py` updated for `route_stop_id`
- [x] Full suite: 486 unit passing, Phase-12-scope integration 39/39 passing, full integration suite passing in isolation (a pre-existing, unrelated cross-file rate-limit test flake was found and flagged separately, not fixed here — see the spawned follow-up task)

## 6. Frontend
- [x] `order.service.ts`/`delivery.service.ts` additions (`assignOrderToRoute`, `loadVehicleForRoute`, `completeRouteReconciliation`)
- [x] Dispatch Board rebuild: status columns, route cards, Route Detail drawer (Load/Start/Cancel/Reconcile), unassigned-orders panel with click-to-assign
- [x] Hardcoded-first-branch bug fixed with a real required branch selector
- [x] Route/nav wiring (`/dispatch`, `routes:read` permission code — was pointing at the never-seeded `delivery:route:read`)
- [x] `nx build dashboard` / lint clean

## 7. Verification
- [x] Backend unit/integration tests (see §5)
- [x] Live browser: order creation → confirm → Dispatch Board unassigned panel → plan route (2-branch selection proving the bug fix) → assign → load vehicle (real warehouse/cylinder stock transfer) → start route → RBAC-correct 403 on `orders:deliver` for admin → order cancellation → **route auto-completed** with zero manual action → reconcile correctly blocked with a 409 + friendly message + Inventory link
