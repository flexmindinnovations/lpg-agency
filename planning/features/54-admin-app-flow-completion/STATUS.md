# Status

Branch `feat/admin-app-stock-moves`, 2026-10-30, on top of `feat/admin-app-order-proof` (PR #88), which stacks on #87, #86, #85, #84, #83, #82; none merged yet. F1, F2 and F3 built.

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

