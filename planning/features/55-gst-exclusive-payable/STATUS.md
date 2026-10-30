# Status

Branch `feat/gst-inclusive-payable`, 2026-10-30, stacked on `feat/driver-handover-upi-qr` (PR #91). Started.

## Backend (done)
- Order lines carry a GST rate snapshot and the order a prices-include-GST flag, taken at confirm and amend with the unit prices. `tax_amount` and `payable_amount` are computed by the order with the invoice's own rounding and returned by the API; `total_amount` stays the price before GST. Orders priced earlier have no snapshot and report `payable_amount` equal to `total_amount`.
- A cylinder type with no GST rate does not stop an order being confirmed; it is left without a snapshot (the invoice still insists on a rate).
- Migration `b7c4e91d3a58` (two nullable columns), applied to the local dev database. OpenAPI spec regenerated and `--check` clean; the Angular generated client regenerated (three added fields).
- Checked: 1,496 backend unit tests pass, ruff, mypy on the touched modules and import-linter (7 kept). On the running dev backend, confirming a booked order returned total 905.50, tax 45.28, payable 950.78 with a 5.00 rate on the line.
- Not covered: backend integration tests against a real database (none run here); the dashboard's order screens, which still show `total_amount`.

