# 70 — Section cards, collecting old empties, driver map, icon row actions

Owner request, 2026-11-27:

1. Use the bordered card style everywhere, particularly in the dashboard.
2. The driver can collect empties from earlier orders while delivering, up to
   what the customer was delivered and has not returned.
3. The map does not load in the Driver app.
4. Row actions are icon-only buttons (red for delete and deactivate), styled
   like the status chips, with a `pTooltip`.

## 1. Section cards (dashboard)

`lpg-section-card` is already the dashboard's panel (Home, Settings, price
list). Use it for every page and drawer section; remove the hand-rolled panel
CSS it replaces. List rows inside a section (an address, a history entry) stay
plain rows. A page whose only content is a toolbar and a table needs no card.

Screens: order detail, cash book, cash handovers, compliance calendar, TDT
rating, inventory, notifications, customer ledger, and the invoice, customer,
complaint, agency and staff drawers.

Add the rule to `AGENTS.md` and a check to `ui-conventions.spec.ts`.

## 2. Empties from earlier orders

**Rule (owner decision, 2026-11-27):** at a delivery the driver may collect, for
each cylinder size, at most what the customer was holding **before** this
delivery (delivered minus returned, as the cylinder ledger records it). Today's
cylinders are full and cannot come back yet. A size that is not on today's order
can be collected too.

Consequences:

- A first-time customer: nothing to collect.
- A customer who held cylinders before using this software shows 0 until the
  office corrects the balance on the Ledger page.
- Today's app caps empties at the number delivered and fills it in by default.
  An old APK would therefore be refused for a customer holding fewer, so the
  new Driver APK should go out with the backend.

Backend:

- `GET /orders/{id}/empties` (`orders:deliver`, the driver's own order):
  `[{cylinder_type_id, cylinder_type_name, quantity_held}]`, one entry for
  every size held, plus every size on the order (possibly 0). Drivers do not
  get `ledger:read`.
- `DeliverOrderRequest.other_empties` (optional): empties of sizes that are not
  on the order. Order lines keep their own `quantity_collected_empty`.
- `DeliverOrderUseCase` refuses more than the held quantity
  (`EMPTIES_EXCEED_HELD`), and a size listed both on a line and in
  `other_empties`, before the delivery code is used up.
- The other sizes are stored on the order (`orders.order.other_empties`, JSONB,
  migration), returned as `OrderResponse.other_empties`, added to the vehicle's
  empties, and written to the ledger with the lines.

Driver app:

- The stop screen reads the held quantities, so they are cached for offline use.
- The delivery screen names each cylinder size, caps "Empties collected" at what
  is held, fills it with the smaller of held and delivered until the driver
  changes it, and offers one more row for each other size held (starting at 0).
- If the quantities were never loaded (offline), the cap is not known: the old
  limit applies, **nothing is filled in** (a filled-in number the server later
  refused would lose a delivery already queued), nothing is added for other
  sizes, and the screen says the server checks when it syncs.
- The "more empties than the van was loaded with" warning assumed one empty for
  one full cylinder, so it goes.

Dashboard: order detail lists the other sizes collected.

Known limit: two deliveries to the same customer recorded offline on one trip
share one cached figure; the server refuses the second if it goes over.

## 3. Driver app map

Reproduced on the emulator with a screen that shows only the map: tiles load
with and without a LocationIQ key. The failure is before the map. An address
added on the dashboard has no coordinates (latitude and longitude are optional
typed fields), so the app looks up the whole one-line address. A full Indian
street address usually returns nothing, and the app shows "Delivery location
not pinned" in place of the map. Checked with a made-up address on the public
OpenStreetMap geocoder: the full line returned no result; locality, city and PIN
code returned one.

Fix in the shared `maps` package (Driver and Customer apps):
`GeocodingService.locate` tries the full address, then its last four parts,
then its last three, then the PIN code. Repeated parts are dropped. At most
four requests, spaced to the free-tier rate limit.

In the Driver app, **Navigate** passes the address text, not the point, when the
point is only approximate; otherwise the driver would be sent to the middle of
the area.

Not changed: the CI test APKs are built without `LOCATIONIQ_API_KEY` (the
repository has no secrets), so they use the public OpenStreetMap tile server.
It works, but its usage policy does not suit production. Adding the key to a
public repository's public APK release exposes it, so that is the owner's call.

## 4. Icon row actions

Change the shared `RowActionCell`: icon only, tinted like a chip (red for
delete and deactivate, primary otherwise), `pTooltip` with the action's words,
`aria-label` naming the row. Narrow the columns. Update the `AGENTS.md` table
and the conventions check.

## Testing

Unit tests for each change; dashboard test, lint and build; backend ruff, mypy,
import-linter, OpenAPI check, unit and integration tests; Flutter analyze and
test for `maps`, `api_client`, `driver_app`, `customer_app`. Screens checked in
a browser with every API call faked. No live data is written.
