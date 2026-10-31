# 54 — Admin app flow completion: run the whole order flow without the web dashboard

## Why
After Waves 1 and 2 (52, 53) the daily work is on the phone, but a few steps of the order flow still force a trip to the web dashboard. The aim here is one acceptance test: from a fresh state, a customer is created, an order is booked, dispatched, delivered, paid, invoiced and closed, stock and cash are settled, with the web dashboard closed throughout.

## Order of work (agreed)
1. **Create customers** — register a customer (with a delivery address) from the phone, add addresses, approve, verify KYC. Today a customer must already exist from the Customer app.
2. **Order screen: payment, invoice, proof of delivery** — the admin cannot see how an order was paid, its invoice, or the delivery proof.
3. **Stock moves** — change status (filled to leaking/damaged), manual adjustment, return to the OMC, the weighment sample after a receipt, stock on each van.
4. **Open bugs** that touch the flow (see 52 STATUS, "Open findings").
5. **Clean end-to-end run** across the three apps from a fresh state, web dashboard closed. Record what was run and what broke.

## Out of scope (stays on the web, by decision)
Creating godowns, branches, cylinder types and GST rates, and registering scales (one-time setup); platform console, feature flags, licences, audit log, reports and GST returns.

## Open decision
Whether the price includes GST (invoice total Rs 950.78 against the Rs 905.50 quoted and collected). Step 2 shows invoice and payment facts as the backend states them and does not change the pricing basis.
