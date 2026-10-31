# Status

Branch `feat/gst-inclusive-payable`, 2026-10-30, stacked on `feat/driver-handover-upi-qr` (PR #91). Built and checked end to end.

## Backend (done)
- Order lines carry a GST rate snapshot and the order a prices-include-GST flag, taken at confirm and amend with the unit prices. `tax_amount` and `payable_amount` are computed by the order with the invoice's own rounding and returned by the API; `total_amount` stays the price before GST. Orders priced earlier have no snapshot and report `payable_amount` equal to `total_amount`.
- A cylinder type with no GST rate does not stop an order being confirmed; it is left without a snapshot (the invoice still insists on a rate).
- Migration `b7c4e91d3a58` (two nullable columns), applied to the local dev database. OpenAPI spec regenerated and `--check` clean; the Angular generated client regenerated (three added fields).
- Checked: 1,496 backend unit tests pass, ruff, mypy on the touched modules and import-linter (7 kept). On the running dev backend, confirming a booked order returned total 905.50, tax 45.28, payable 950.78 with a 5.00 rate on the line.
- Not covered: backend integration tests against a real database (none run here); the dashboard's order screens, which still show `total_amount`.

## Apps (done)
- `api_client`: `OrderResponse.taxAmount`, `payableAmount` and `amountToPay` (the payable amount, or the total from an older server); `OrderLineResponse.gstRatePercent`.
- **Driver app:** the stop says "Collect Rs 950.78 (includes GST Rs 45.28)" and the amount on Record delivery starts at Rs 950.78. The cash handover's expected cash therefore matches the invoice.
- **Admin app:** the order screen shows Price before GST, GST and Total to pay; the deliver sheet starts at the amount to pay.
- **Customer app:** the order shows Price, GST and "You pay"; the list shows the amount payable. An order priced before GST was recorded still shows "Rs X + GST".
- Tests: api_client 127, driver 103+, admin 103, customer 66 (new ones for the amounts in each).

## End-to-end check (local dev, Admin and Driver on one emulator)
A fresh order ORD000063, Domestic 14.2kg at Rs 905.50, 5% GST:
1. Admin order screen after confirming: Price before GST Rs 905.50, GST Rs 45.28, Total to pay Rs 950.78.
2. Driver: "Collect Rs 950.78 (includes GST Rs 45.28)"; choosing UPI showed the QR for Rs 950.78 with the agency's payee and UPI ID, and the amount field also Rs 950.78.
3. Delivered by UPI: the invoice (INV-2026-000015, total Rs 950.78) was **Paid**, still due Rs 0.00. Before this change the same order ended "partially paid" with Rs 45.28 due.
4. Also confirmed on a fresh order: the "Check your van load" card clears by itself within seconds of confirming the load (the earlier Driver Today bug).
Not run: the cash path of a GST order (cash handed over then accepted), the Customer app against a live order, the web dashboard (still shows the price before GST).

## Still true after this change
- Orders confirmed before this change have no GST snapshot, so their payable amount equals their total as before; the invoice still adds GST when it is issued. Only new and re-confirmed orders show the split.
- The invoice resolves the GST rate when it is issued, not from the order's snapshot.

