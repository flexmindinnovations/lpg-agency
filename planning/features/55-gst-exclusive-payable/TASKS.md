# Tasks

## Backend
- [x] G1 Domain: order lines carry a GST rate snapshot, the order a prices-include-GST snapshot; `tax_amount` and `payable_amount` computed with the invoice's rounding (+ unit tests)
- [x] G2 Persistence: columns, migration, repository mapping
- [x] G3 Confirm and amend resolve the GST classes and take the snapshot (+ tests)
- [x] G4 API: `tax_amount`, `payable_amount` on the order response, `gst_rate_percent` on its lines; OpenAPI spec regenerated

## Apps
- [x] G5 api_client models
- [x] G6 Driver app: Collect and the amount prefill are GST-inclusive
- [x] G7 Admin app: order screen shows price, GST and total; deliver sheet and lists use the payable amount
- [x] G8 Customer app: what the customer owes includes GST
- [x] G9 End-to-end check: order, QR, cash and invoice all say the same amount

## Deferred
- [ ] Angular dashboard order screens
- [ ] Invoice reads the order's GST snapshot
