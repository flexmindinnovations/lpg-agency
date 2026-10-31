# Tasks

## C1 Compliance alerts (done)
- [x] C1.1 API client: list compliance documents (owner and expiry filters), replace (renew); models and tests
- [x] C1.2 Alerts screen: summary, grouped by urgency (expired / within 30 days / within 90 days), owner names, More item with badge, dashboard attention card
- [x] C1.3 Document sheet and Renew (photo, number, issue and expiry dates)
- [x] C1.4 Tests, emulator run, PR

## C2 Pricing (done)
- [x] C2.1 API client: price list, set a price, OMC rate proposals (list, accept, reject); models and tests
- [x] C2.2 Pricing screen: current price per cylinder type and customer type (and branch), scheduled changes, More item
- [x] C2.3 Change or add a price (with a check on a large jump); price history in the sheet
- [x] C2.4 Review OMC rate proposals (accept / reject)
- [x] C2.5 Tests, emulator run, PR

## C3 Employees
- [ ] Not started

## C4 Users and roles
- [ ] Not started

## Discovered / deferred
- [ ] Pricing: scheduling a price for a future date from the phone (the API supports `effective_from`; the sheet always starts a price now).
- [ ] Pricing: which price GST is on. The invoice total is higher than the price shown to customers (open finding in 52); the price list itself does not say whether it includes GST.
- [ ] Verify or reject a document (compliance:verify) on the phone; stays on the web for now.
- [ ] Per-user permission overrides on the phone.
- [ ] Compliance alerts: the owner's own licence expiry on a driver's profile is a separate field from the compliance documents; renewing one does not update the other. Check which the web treats as the source of truth.
