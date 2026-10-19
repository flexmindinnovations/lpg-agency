# 44 — Book only orderable cylinders — Plan

## Problem (reported 2026-10-19)

Booking did not check stock or pricing. The dashboard booking form listed
every cylinder type, including inactive ones; the Customer App listed every
active type. A booking for an unpriced type was accepted and failed only at
confirmation ("No price configured"), and nothing checked stock at all until
a van was assigned.

What was checked before this change:

| Check | Create (`POST /orders`) | Confirm | Dashboard form | Customer App | WhatsApp |
|---|---|---|---|---|---|
| Type active | no | no | no | yes (client filter) | yes |
| Price set | no | yes (404) | no | no | shown, not enforced |
| Filled stock | no | no | no | no | no |

## Rule

A cylinder type is orderable for a customer at a branch when it is active, a
price is in effect for the customer's type at that branch (branch override,
else tenant-wide default), and the branch has filled cylinders left:

    filled in the branch's active warehouses + filled on the branch's vehicles
    − quantity_ordered of the branch's booked/confirmed orders
    − quantity_pending (backorder) of its assigned/ready/out-for-delivery orders

Vehicle filled stock is already net of reservations made at assignment, so
assigned orders only count their unreserved backorder.

## Changes

- `application/order/orderable.py`: `OrderableCylinderTypes.list()` and
  `.require()`. New port `BranchStockReader`, implemented by
  `SqlAlchemyBranchStockReader` (`repositories/order.py`).
- `CylinderNotOrderableError` (409, `CYLINDER_NOT_ORDERABLE`), naming the
  cylinder and the reason.
- `CreateOrderUseCase` refuses a non-orderable line before drawing an order
  number; `ConfirmOrderUseCase` re-checks, leaving the order's own booking out
  of the demand.
- `GET /api/v1/orders/orderable-cylinder-types` (`orders:create`): staff pass
  `customer_id` (branch defaults to the customer's); a customer login gets
  its own list.
- WhatsApp assistant lists and quotes only orderable types.
- Dashboard booking form loads the list for the selected customer and shows
  price and stock; Customer App order screen uses the same list and caps the
  quantity at what is in stock.

Dispatch and van-loading are out of scope (another thread).

## Concurrency (added 2026-10-19)

The check and the insert it allows must be one step, or two bookings can
both read the same free stock. `OrderableCylinderTypes.require()` first calls
`BranchStockReader.lock_branch_for_booking()`, which takes
`pg_advisory_xact_lock(hashtextextended('order-booking:<branch_id>', 0))`.
PostgreSQL releases it when the use case's transaction commits or rolls back,
so a concurrent booking at the same branch waits and then reads stock that
includes the first order. Bookings at other branches are not blocked, and
listing takes no lock.
