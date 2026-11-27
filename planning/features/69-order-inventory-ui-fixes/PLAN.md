# 69 — Order booking, order price and stock correction fixes

Reported by the product owner on 2026-11-27 from the dashboard.

## Problems and decisions

1. **Customer search in New Booking** opens nothing on click and needs two
   characters. It becomes a dropdown with search: clicking or the arrow button
   lists the first customers; typing searches name, phone or consumer number.
2. **Quantity on a booking line** is squeezed to nothing by a long cylinder
   label. The cylinder list shrinks (with an ellipsis); quantity keeps a fixed
   width.
3. **Action columns have no heading** (branches, warehouses, cylinder types).
4. **No price on a booked order.** Unchanged rule: the price is fixed when the
   agency confirms the order. The order detail shows an **estimate** at today's
   prices, clearly labelled, computed by the same domain sums as confirmation.
   Nothing is saved. Only `GET /orders/{id}` returns it.
5. **No way to remove stock.** Unchanged rule: the stock ledger is never
   edited or deleted (BR-06); a correction is a new entry. The existing
   Reconcile (physical count + approval) is made discoverable: a "Correct
   count" action on each balance row, prefilled. Rows at zero leave the
   balance table; history and the stock register keep them. The on-screen text
   now says who can approve (an agency admin can approve their own count).

## Added the same day: UI conventions on every screen

The owner pointed out that the new customer field did not match the other
dropdowns, and asked for the same conventions everywhere. They are now rules in
`AGENTS.md` ("Dashboard UI conventions"):

1. Every dropdown has a search box. Customer fields (New Booking, Raise
   Complaint) use one shared `lpg-search-select`: the same `p-select`, searched
   on the server. This replaces decision 1 above.
2. A state in a table row is a chip, including the Employees "App login".
3. Row actions are one "Actions" column of buttons with an icon and text
   (`rowActionsColumn`), not underlined text.
4. Unit tests are added and run once the features are done.

`apps/dashboard/src/app/ui-conventions.spec.ts` checks rules 1 to 3 in CI.

## Out of scope

- Prices on the order list and in the mobile apps for unconfirmed orders.
- Deleting inventory records or ledger entries.
- Blocking domestic cylinders for business customers (separate task).
- Forms that disable their submit button while incomplete instead of showing
  what is missing (found during this work; about 30 forms).

## Testing

Backend unit tests for the estimate; Angular unit tests for the search field,
order detail, inventory and grid headings; a browser check with the API faked
(never against live data).
