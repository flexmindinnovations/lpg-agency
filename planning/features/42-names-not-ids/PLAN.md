# 42 — Names instead of ids in the dashboard — Plan

## Problem

Reported 2026-10-19: confirming an order showed "No price configured for
cylinder type bc4ace92-…", and the Pricing table's Branch column showed branch
UUIDs. Staff can't act on an id. Asked: show names everywhere.

## Sweep result

Every dashboard grid and detail view was checked for raw ids. Most already
resolve names client-side (`valueFormatter` + a name map). Three gaps remained:

- **Pricing grid:** Branch showed `branch_id`; there was no cylinder type column.
- **Complaint detail:** the linked order showed a short id.
- **Server error messages:** domain errors (insufficient stock, ledger
  balance, delivery over reservation, missing price) embed the cylinder type
  UUID, because aggregates only know cylinder types by id. A few order/route
  messages embedded order or route UUIDs.

## Changes

- **API (`dependencies/unit_of_work.py`):** when an `ApplicationError` or
  `DomainError` carries `cylinder_type_id` in its context and its message
  contains that id, the id is replaced with the cylinder type's name, read
  through `CylinderTypeRepository` on a fresh tenant-scoped session. One place
  instead of ~27 call sites; best effort (lookup failure keeps the message).
- **Confirm order:** the missing-price message also names the customer type
  and says to add the price under Pricing.
- **Delivery:** "already assigned" messages use the order number; route
  reconciliation and route-assignment messages drop the raw ids.
- **Dashboard Pricing:** rows are mapped to `cylinder_type_name` and
  `branch_name` (tenant-wide default reads "All branches"), so the grid shows,
  sorts, filters and searches by name. New Cylinder Type column.
- **Dashboard Complaints:** detail drawer fetches the linked order's number
  (only for viewers with `orders:read`), falling back to the short id.
