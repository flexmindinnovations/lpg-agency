# Tasks

## A. Foundation
- [x] A1 Navigation: 4 tabs + More; bell with badge and search in the app bar (checked on the emulator)
- [~] A2 Look and feel: new app bar, metric tiles, More menu and dashboard done; Orders, Dispatch, Fleet and detail screens still use the old cards
- [x] A3 Live, tappable dashboard (realtime + 45 s refresh; tiles for complaints, stock and invoices become links as B-modules land)
- [x] A4 Global search (orders, customers, invoices) + orders list deep links; customer and invoice hits become tappable with B1/B2
- [x] A5 No free van / driver: who holds them, open that trip, add a driver or van (code and unit-level checks only; not yet exercised on the emulator because 1 of 3 vans is free on dev data)
- [x] A6 Admin app icon (adaptive) and in-app logo

## B. Wave 1 modules
- [x] B1 Customers: search list, detail (outstanding, cylinders held, recent orders and invoices, contact and addresses), Call, New order prefilled for the customer
- [x] B2 Invoices: list with search, status and customer filters; detail with GST split and payments; record payment (cash, UPI, card, cheque, bank transfer); UPI QR; send/remind
- [x] B3 Complaints: list with status filters and overdue marking, detail with deadline, customer and order links, assign/reassign, resolve with outcome and note; dashboard tile, attention card and More badge
- [ ] B4 Stock
- [x] B5 Cash book: day picker (step or pick, never past today), collected by method, driver handovers (expected / handed over / short / excess), office check (accepted / disputed / still to check, linking to Approvals), cash each driver holds now; More item and the dashboard cash tile open it

## Discovered / deferred
- [ ] Font change (Inter is bundled and kept); a different typeface needs a font file to be added to the repo.
- [ ] Wave 2: pricing, users and roles, employees, compliance alerts.
