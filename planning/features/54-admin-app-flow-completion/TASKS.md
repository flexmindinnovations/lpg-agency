# Tasks

## F1 Create customers (done)
- [x] F1.1 API client: register customer, approve customer, verify KYC document (+ tests)
- [x] F1.2 Add customer screen (Customers list button; "Add new customer" from New order): validation for mobile, pincode, GSTIN, contact person for businesses
- [x] F1.3 Customer page: add address, approve (assigns the consumer number), KYC documents with verify / reject
- [x] F1.4 Tests, emulator run, PR

## F2 Order screen: payment, invoice, proof of delivery (done)
- [x] F2.1 API client: proof of delivery, invoices filtered by order (+ tests)
- [x] F2.2 Order screen: Delivery section (when, collected at the door, location, signature and photo) and Payment and invoice section (invoice summary, link to the invoice)
- [x] F2.3 Tests, emulator run, PR

## F3 Stock moves (done)
- [x] F3.1 API client: status rules, change status, manual correction, return to the OMC, receipt weighment sample (+ tests)
- [x] F3.2 Stock screen: Change status, Correct stock, Return to OMC (with the server's status rules and the system's quantity shown)
- [x] F3.3 Weighment sample offered after Receive stock (optional, skippable)
- [x] F3.4 Stock on each van
- [x] F3.5 Tests, emulator run, PR

## F4 Open bugs (done, with two left open on purpose)
- [x] Add driver / Add van submit button under the gesture bar: not reproduced (see STATUS)
- [x] Driver cash screen says "Matches the expected" for a count that is Rs 0.50 short
- [x] Driver Today does not refresh after the last delivery, and keeps the "Check your van load" card
- [x] Unhandled WebSocketChannelException when the socket cannot connect (all three apps)
- [x] Customer app shows a stale order status after being in the background
- [ ] Stale dev trips hold the only seeded van: dev data, not code; clean it in the dev database or by settling those trips
- [ ] Invoice total (Rs 950.78) against the price quoted and collected (Rs 905.50): needs the owner's decision on whether the price includes GST

## F5 Clean end-to-end run (done; findings below)
- [x] Run the flow with the web dashboard closed: create customer, book, confirm, add driver and van, send out, driver signs in and delivers, cash declared, order closed, cash accepted
- [x] Fix what broke: New order crash from a customer page, crash after booking, Driver Today stale after a queued action
- [ ] Decide whether the price includes GST (every order ends "partially paid" until then)
- [ ] Decide whether the office should need a note for a shortfall under a rupee (the Driver app says none is needed)
- [ ] Say which branch lacks stock or a price when "Nothing can be booked" appears
