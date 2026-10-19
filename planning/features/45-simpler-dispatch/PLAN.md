# 45 — Simpler dispatch (trip sheet) — Plan

## Problem

Reported 2026-10-19: dispatch and van loading in the dashboard were confusing.
Today's flow took up to seven actions across two screens:

1. Dispatch → Plan Route (branch, date, driver, vehicle).
2. Assign each order to the route, one drawer per order (or Add Stop).
3. Open the route → Load Vehicle → type each cylinder type and quantity, with no stock shown.
4. Orders page → open each order → Dispatch (`assigned → ready_for_dispatch`), or the driver sees "Waiting for dispatch".
5. Start Route (overlaps with the driver's first departure).

Steps 2 and 3 in that order were a trap: assigning before loading reserves
nothing on the empty van (D-08 backorder), so the driver can't record the delivery.

## Design — the distributor's trip sheet

One drawer: driver and van → tick the orders → load sheet (needed, already on
van, spare, to load, in godown) → **Load & dispatch**. See ADR-056.

## Changes

- **Domain:** `Order.reserve_backorder()`; `Route.add_to_load_manifest()`.
- **Application:** `LoadAndDispatchRouteUseCase`; the weighment gate is extracted to `LoadOutWeighmentGate` and shared with `LoadVehicleForRouteUseCase`.
- **API:** `POST /routes/{id}/load-and-dispatch` (`routes:manage`), body `{warehouse_id, order_ids, extra_lines}`.
- **Dashboard:** Dispatch page rebuilt around the trip sheet drawer; trip detail shows Load & dispatch / Add orders, what was loaded and whether the driver checked the van; columns renamed.
- **No migration. No Driver App change.**

## Tests

- Unit: `tests/unit/test_load_and_dispatch_route.py` (11 cases).
- Integration: `TestLoadAndDispatchThroughRealStack` in `test_route_endpoints_smoke.py` (backordered order released and delivered, short godown moves nothing).
- E2E: `order-to-delivery-workflow.spec.ts` uses Load & dispatch.
