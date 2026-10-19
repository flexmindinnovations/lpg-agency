# 42 — Post-delivery customer actions — Tasks

- [x] Record the driver's doorstep collection on the generated invoice
- [x] Backfill doorstep payments onto existing invoices (migration `c8d4e2f6a1b3`)
- [x] Refuse payment links for paid/cancelled/refunded invoices
- [x] Customer App: refetch order/invoice detail on every visit, pull-to-refresh
- [x] Customer App: Cancel only for cancellable statuses
- [x] Unit and widget tests

## Follow-ups (not in scope)

- Driver app should show when an order was already paid online, so the driver
  does not collect again (over-collection is now capped on the invoice and
  logged as `doorstep_collection_exceeds_invoice`, but still counts in the
  driver's expected cash).
