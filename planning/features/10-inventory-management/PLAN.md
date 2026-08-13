# Phase 10 — Inventory Management

## Goal

Implement warehouse and vehicle cylinder inventory tracking: balances by
`(cylinder_type, status)`, goods receipt (GRN), warehouse→vehicle load
transfers, delivery/collection, status changes, manual adjustments, and
reconciliation — across the backend and Angular dashboard.

`InventoryLocation` is the sole aggregate root of the `inventory` bounded
context; GRN and reconciliation records are entities of it, persisted as
plain append-only/two-step records rather than loaded through the
aggregate.

## Scope

- **Backend:** `inventory` schema migration (5 tables, RLS, permissions),
  `InventoryLocation` domain aggregate, application use cases (lazy
  create-on-first-use), infrastructure repositories (materialized balance
  projection kept in lockstep with the transaction ledger), FastAPI router
  (10 endpoints).
- **Frontend:** Angular lazy-loaded `feature-inventory` library — location
  picker, balance grid, transaction history, 6 action drawers (Receive
  Goods, Load Transfer, Delivery/Collection, Change Status, Adjust,
  Reconcile), sidebar nav link.
- **Tests:** unit (domain + use cases), integration (endpoint smoke, RBAC
  incl. `reconciliation:approve`'s live recheck, balance/transaction
  lockstep + RLS cross-tenant isolation).

## Key domain decisions

- **`filled ⇄ empty` are not a literal same-location status transition.**
  `filled → empty` decomposes into `record_delivery` (vehicle Filled
  decrements) and, independently, `record_collection` (vehicle Empty
  increments) — proven non-1:1 by BR-13's own worked example (Filled
  50→35 delivering 15; Empty 10→24 collecting 14). `empty → filled` only
  happens via `receive_goods` (the GRN cycle). The generic
  `change_status`/`adjust` transition graph excludes both pairs by
  construction; attempting either raises `409 INVALID_STATUS_TRANSITION`.
- **Lazy create-on-first-use, applied uniformly.** Every use case resolves
  its `InventoryLocation` by `(location_type, location_ref_id)` — a
  warehouse or vehicle id — never by an opaque `inventory_location_id`. A
  never-touched location has no persisted row; balance/transaction reads
  return all-zero/empty, not 404. This is why the API addresses locations
  as `/inventory-locations/{location_type}/{location_ref_id}/...` rather
  than by a client-discovered id.
- **`InventoryLocation.reconcile()`** sets the tracked balance directly to
  a physically-counted `actual_quantity` and records the signed delta as a
  `reconciliation` transaction (or none, if the count matched exactly) —
  distinct from `adjust()`, which moves stock between two named statuses.

## Out of Scope for this Phase

- Order Management / stock reservation (Phase 11+).
- Cylinder Ledger (customer-held cylinder tracking, Phase 12+).
- A list endpoint for reconciliation records (approval is only reachable
  immediately after creating a record in this phase's UI).

## References

- `docs/data/01-domain-model.md` §4.6/§7/§8 (`InventoryLocation`)
- `docs/data/03-database-schema.md` Schema: `inventory`
- `docs/data/08-state-machines.md` §5 (cylinder status transitions)
- `docs/data/17-api-security.md` §6/§7 (permission matrix, live-recheck list)
- `docs/business/business-rules.md` BR-11–BR-15
