# Phase 11: Order Management Status

> Backfilled 2026-08-19 (R8). No PLAN/TASKS/STATUS ever existed for this
> phase before, despite it being fully built, fully tested, and fully
> wired on the frontend — `planning/MODULE_STATUS.md`'s own row for this
> phase notes `planning/features/11-order-management/` "still does not
> exist" as its only open item. This file closes that gap; nothing in the
> implementation itself needed fixing to write it (unlike Phases 16/17/
> reporting, which needed real bug fixes first).

## Current Status
- **State:** ✅ **COMPLETE** — backend and frontend implemented, tested, and verified.

## Backend — ✅ complete and independently verified

- [x] Domain model (`Order` aggregate — 10 states, `OrderLine` backorder/over-delivery handling, `DeliveryAddress` snapshot, 6 domain events, 2 domain errors)
- [x] Application use cases (13, covering the full lifecycle plus reads)
- [x] Repository implementation
- [x] Alembic migration (`7c3f1a9e2b4d`), plus the historical `de56730bb88f` migration debt closure (see Completion Notes)
- [x] REST API (16 endpoints under `/orders`, one live-checked)
- [x] Gates: ruff, mypy, all 5 import-linter contracts, full unit + integration suites green
- [x] Domain unit tests (`test_domain_order.py`), use-case unit tests (`test_order_use_cases.py`), through-the-stack integration tests (`test_order_endpoints_smoke.py` — full lifecycle, failed-delivery→reschedule, both cancel paths, illegal-transition 409, role-scoping, cross-tenant isolation) and RBAC tests (`test_order_rbac.py`, including the live-check class)

### An open, currently-true gap — not fixed by this backfill

**BR-04 (cylinder cap) and BR-19 (credit limit) are not actually enforced
at `confirm()`.** The ports (`CylinderCapPolicy`, `CreditLimitEvaluator`)
are real and wired into `ConfirmOrderUseCase` via dependency injection —
but the only adapters that exist, `PermissiveCylinderCapPolicy`/
`PermissiveCreditLimitEvaluator` (`infrastructure/order/policies.py`), are
unconditional no-ops. Their own docstrings say this is deliberate,
deferred to Cylinder Ledger (Phase 13) and Accounting (Phase 14) supplying
real data — but **both of those phases have since shipped**, and nobody
has come back to wire a real adapter in. This is not tracked as a C-numbered
finding anywhere else in `planning/MODULE_STATUS.md`; recording it here so
it isn't lost. Swapping the adapter is the entire fix — the use case and
port contract need no changes (`git grep PermissiveCylinderCapPolicy` /
`PermissiveCreditLimitEvaluator` finds the one call site each).

### Two defects this phase's own tests surfaced, both already fixed

1. **(C1, R1, 2026-08-18)** The Create Order drawer's delivery-address
   dropdown used `optionLabel="address_line"` against
   `CustomerAddressResponse`, which only has `line_1` — every option
   rendered blank. Fixed.
2. **(C9/C10, R11, 2026-08-18)** `get_unit_of_work`'s catch-all was
   downgrading every `DomainError` — including this aggregate's own
   `InvalidOrderStatusTransitionError` — to a generic 500 instead of the
   documented 409. Order-transition integration tests were among the ones
   that first exposed it, though the defect itself was a shared,
   cross-cutting dependency bug, not something specific to Order's own
   code. Fixed at the shared dependency.

## Frontend — ✅ complete and verified

- [x] Nx library scaffolded (`@lpg/order/feature-orders`)
- [x] Order Queue (list + inline Create Order drawer)
- [x] Order Detail (all lifecycle actions — Confirm/Dispatch/Depart/
      Reschedule/Close/Approve-cancellation as direct buttons gated by
      computed signals; Assign/Failed-Delivery/Deliver/Cancel as drawers;
      the Deliver drawer includes a signature-pad canvas, photo upload, GPS
      capture, and OTP entry)
- [x] `order.service.ts` in `libs/shared/data-access`
- [x] Wired into `app.routes.ts` (`orders:read` guard) and shell nav
- [x] Live browser verification + full frontend gate (done at original ship time)

## Completion Notes

1. This migration's own docstring once documented "PHASE 11 MIGRATION
   DEBT" — an interim `driver_id`/`vehicle_id` pair stored directly on
   `orders.order` because Route/RouteStop didn't exist yet at the time
   (under an older phase-numbering scheme where Route was itself briefly
   called "Phase 11", before Order claimed that number and Route/Dispatch
   became Phase 12). That debt is fully closed: `de56730bb88f` added
   `route_stop_id` and dropped the interim columns; no backfill was
   mechanically needed since no production tenant existed yet. Current
   domain code has no trace of the old columns.
2. Order Management was never part of C4's "zero test coverage" finding —
   it already had thorough backend and frontend test coverage at ship
   time. The gap this backfill closes is purely documentation, not code.
3. `POST /orders/{id}/cancel/approve` is one of a small, deliberately-short
   list of live-DB-checked (not claims-based) permissions in this codebase
   — the consequence of approving a cancellation (releasing reserved
   inventory, charging or waiving a fee) is high enough that a stale JWT
   claim surviving a just-revoked permission is treated as unacceptable
   risk, unlike the other 15 endpoints here.
