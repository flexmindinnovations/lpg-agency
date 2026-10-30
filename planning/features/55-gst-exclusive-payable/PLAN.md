# 55 — Amount payable on an order includes GST (prices are GST-exclusive)

## Why
The agency's prices are before GST. The invoice already adds GST on top (Rs 905.50 + 5% = Rs 950.78), and the UPI QR is built from the invoice. But the order itself only ever carried the pre-GST price, so the app told the driver to "Collect Rs 905.50" and the cash handover, the customer's order total and the office's order screen all said Rs 905.50 while the invoice and the QR said Rs 950.78. Every order ended "partially paid", and a UPI customer paid Rs 45.28 more than a cash customer.

## Decision (owner, 2026-10-30)
Prices are GST-exclusive. GST is calculated and the customer pays price plus GST everywhere; the QR is GST-inclusive; the invoice shows the price and the GST separately and correctly.

## Design
- The backend already has a tenant setting `prices_include_gst` (default off = exclusive) and the invoice handles both. Nothing about the invoice changes.
- An order snapshots, when it is confirmed or amended, each line's GST rate and whether prices include GST, next to the unit-price snapshot it already takes (so a later rate change does not move an order already quoted).
- The order computes `tax_amount` and `payable_amount` itself with the same rounding as the invoice (per line, half-up to the paisa), and the API returns them. `total_amount` stays the price before GST so nothing that reads it breaks.
- Orders confirmed before this change have no snapshot: they report no tax and `payable_amount` equal to `total_amount`, as before.
- The apps show the GST-inclusive amount wherever the customer is asked to pay or sees what they owe, and the split (price, GST, total) on the order screen.

## Out of scope
- The Angular dashboard's order screens still show `total_amount`.
- The invoice keeps resolving the GST rate when it is issued rather than reading the order's snapshot; a rate changed between confirmation and delivery would make the two differ. Noted, not changed.
- Partial deliveries: the amount to collect is for the quantities ordered, as the app already did.
