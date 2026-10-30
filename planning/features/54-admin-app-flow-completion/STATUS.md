# Status

Branch `feat/admin-app-flow-bugs`, 2026-10-30, on top of `feat/admin-app-stock-moves` (PR #89), which stacks on #88, #87, #86, #85, #84, #83, #82; none merged yet. F1 to F4 built.

## F1 Create customers
Built on `POST /customers`, `POST /customers/{id}/approve`, `POST /customers/{id}/addresses` and `POST /customers/{id}/kyc/{docId}/verify`; no backend change.
- Customers list has an Add button; New order's customer picker has "Add a new customer". Either opens the Add customer form (type, name, mobile, optional second number and email, GSTIN and contact person for businesses, branch when there are several, and a delivery address with city and PIN code). A new customer starts "Onboarding", which can already book.
- The customer page offers Approve (assigns the next consumer number), Add address, and an Identity documents section where a waiting document can be verified or rejected with a reason. The GSTIN shows under contact details.
- Validation: 10-digit mobile, 6-digit PIN, GSTIN pattern, contact person required for commercial (the backend rule), email shape.
Tried on the emulator against the local backend: Add customer (Sunita Walk-in Test, domestic, Kondhwa branch, Pune address) landed on the new customer's page showing "Not approved yet"; Approve made them Active with consumer number CN-000112. That customer is left in the dev database.
Not tried on the emulator: the New order picker entry, a business customer, Add address, and verifying or rejecting a KYC document (the review sheet and the two API calls are covered by tests; no dev customer has a submitted document). Whether a KYC photo shows depends on the backend returning a fetchable URL.
`CustomerResponse` now carries `gstin`. The customer-type labels moved to a shared file used by Pricing and Add customer.

## F2 Order screen: payment, invoice, proof of delivery
Built on `GET /orders/{id}/proof-of-delivery` and `GET /invoices?order_id=`; no backend change. A delivered or closed order now shows two sections under its total.
- **Delivery:** when it was delivered, what was collected at the door and how, a link to the place on the map, the OMC delivery code when there is one, and the signature and photo (tap to see full size) when the driver took them.
- **Payment and invoice:** the order's invoice as a row (opens the invoice) with total, paid so far and still due. When something is still due after a collection at the door, a note says what the driver collected against the invoice and points to the invoice to record a payment.
Tried on the emulator against the local backend, on ORD000061 (closed): both sections, and the invoice row opening INV-2026-000013. That order's driver took no signature or photo, so the pictures were not seen on a device (widget tests cover them being absent; the image-loading path is not exercised).
**It makes the open GST question visible:** the order total is Rs 905.50 and the invoice total Rs 950.78. The screen shows both as the backend states them; it does not decide which is right.
Not tried: an order whose invoice still has a balance (the one used had been settled earlier), an order delivered without an invoice.

## F3 Stock moves
Built on the existing inventory endpoints; no backend change. On the Stock screen, under "Other stock actions":
- **Change status** (filled to leaking or damaged, and so on) and **Correct stock** (a fix to the books, with a reason kept on record). The options come from the server's own transition rules, so a move it would refuse is never offered; the sheet shows how many the system holds and will not accept more.
- **Return to OMC:** empties or defective cylinders back to the plant, with the plant, challan and truck, producing a return number.
- **Weigh a sample** is offered after every Receive stock (a tenth of the batch suggested, a scale chosen from those at the godown, underweight found). It is optional, never holds up the receipt, and says so when the godown has no scale (scales are registered on the web).
- **On the vans:** what each active van in the godown's branch is carrying.
Tried on the emulator against the local backend: the vans list (TS09UA3320 carrying 10 Commercial 19kg and 30 Domestic 14.2kg), Change status (1 Domestic 5kg filled to leaking: showed as "Moved between statuses", only Damaged and Leaking offered for filled), then Correct stock (leaking back to filled with a reason: "Corrected by hand"); the dev godown's filled total is back to 808.
Not tried on the emulator: Return to OMC (it would change dev stock; covered by an API test and the sheet's checks by widget tests) and the weighment sample (no scale is registered at the dev godown; the no-scale message and the checks are widget-tested).

## F4 Open bugs
- **Add driver / Add van button under the gesture bar: not reproduced.** On the emulator, with the form scrolled to the end and again after typing in a field and closing the keyboard, the button sat about 250 px above the gesture bar. No code change. If it shows up on a particular phone, the screenshot and the phone model would help.
- **"Matches the expected" for a short count: fixed.** A difference under a rupee still needs no reason (that mirrors the server), but the label now says "Short by Rs 0.50. Under a rupee, so no reason is needed." and only an exact count says "Matches". Test updated.
- **Driver Today not refreshing: hardened, cause not pinned down.** I could not reproduce it without running a full delivery. After a delivery the cash to declare and the cash in hand are now invalidated along with the route; confirming the van load also refreshes the load; pull to refresh now reloads the whole screen. Worth watching in the end-to-end run (F5).
- **Unhandled WebSocketChannelException: fixed.** When the socket could not connect, the connection's `ready` future failed with no listener and escaped as an unhandled exception even though the client reconnects correctly. It is now handled at the source. A test that connects to a closed port failed before the fix and passes after.
- **Customer app stale after being in the background: hardened.** The shell now reloads orders, invoices and notifications when the app returns to the foreground, as the Driver shell already did. No widget test for this one (the shell needs a router to build); analyze and the existing tests pass.
- Left open on purpose: stale dev trips (dev data) and the GST price question (needs a decision).

## F5 Clean end-to-end run (2026-10-30, one emulator, three apps, local backend, web dashboard not used)
Steps run, in order, and what happened:
1. **Admin: Add customer** "Fresh Flow Customer" at the Gachibowli West branch (the first customer, at Kondhwa, could not book: that branch has no stock). New, not yet approved: could book straight away.
2. **Admin: New order** from the customer's page, Domestic 14.2kg at Rs 905.50. **Crashed** (see below). After the fix: booked as ORD000062, confirmed.
3. **Admin: Send out** found no driver or van in that branch (the Wave 1 blocker panel). **Added a driver** (Meera Joshi, licence photo from the gallery, with Driver App login) and **a van** (TS09XY7777) from the panel's own buttons, then "Load and send out": order Ready for dispatch.
4. **Driver app:** signed out the previous driver and signed in as Meera with the code (the Driver App login made in step 3 worked). Confirmed the van load, started the delivery, recorded it with the customer's code, a signature and Rs 905.50 cash. **Today showed "Cash in hand" and "Cash reconciliation pending" immediately**, no restart.
5. **Driver app: cash handover:** counted Rs 905 against Rs 905.50: "Short by Rs 0.50. Under a rupee, so no reason is needed." Declared CSH000007.
6. **Admin:** the order showed Delivered with the Delivery section (when, Rs 905.50 cash, map link, signature) and Payment and invoice (INV-2026-000014, partially paid, Rs 45.28 due, with the explanation). Closed the order. Approvals: accepted the handover (a note was required for the Rs 0.50 shortfall). Stock showed "Sent out on a van -1" and the new van.

**Found and fixed in this run**
- **Admin: opening New order from a customer's page crashed** (red screen, a navigator assertion). The form lived in the Orders tab's navigator but was pushed from a page above the tabs. It is now a full-screen route above the tabs.
- **Admin: booking an order crashed the same way** on the way to the new order's page. It now goes to the order with `go`, so Back returns to the Orders list. (The booking itself had succeeded both times; only the screen after it failed.)
- **Driver: "Check your van load" stayed after confirming** (the earlier report, now understood). The Driver app queues its actions, and the route was re-read before the queued confirmation reached the server; nothing read it again once the queue drained. The route, history and cash reads now repeat whenever the queue's size changes. Checked live: the cash cards appeared at once after the last delivery. The van-load card itself was not re-tested on a fresh order (the load was confirmed before the new build); a unit test covers the refetch-on-drain mechanism.

**Open, needs a decision or is a limit of the dev setup**
- **Every order ends "partially paid".** The customer is quoted and pays Rs 905.50 but the invoice is Rs 950.78 (5% GST on top). The order screen now shows both honestly with Rs 45.28 due. Whether the price includes GST decides which number changes.
- **Rs 0.50 shortfall:** the Driver app says no reason is needed (under a rupee), the office screen still asks for a note to accept it.
- **"Nothing can be booked for this customer"** does not say that the customer's branch has no stock or no price. A customer registered at a branch without a godown cannot book, and the message does not help.
- **The signature picture did not load on the emulator:** the dev file server link is `http://localhost:59000/...`, which the emulator cannot reach. The screen shows a placeholder. Not verifiable here; works if the link is reachable.
- **The Admin app signed out partway** (session lifetime); signing back in worked.
- **Not part of this run:** a booking that starts in the Customer app (covered in the earlier run), Return to OMC, KYC verification, Add address.

