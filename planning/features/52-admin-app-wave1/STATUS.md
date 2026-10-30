# Status

Branch `feat/admin-app-wave1`, 2026-10-29. Phase A done except the wider look-and-feel pass; Phase B (Customers, Invoices, Complaints, Stock, Cash book) not started.

## End-to-end run (three apps, one emulator, local backend, debug builds)
Customer books (cash on delivery) -> Admin confirms -> Send out blocked (no free driver) -> Admin adds a van and a driver (with app login) from the blocker panel -> Admin sends out -> Driver signs in by OTP, confirms van load, starts the delivery, records it with the customer's delivery code -> invoice created automatically -> Admin closes the order -> Driver declares cash (note count) -> Admin reviews and accepts. Every step worked after the fixes below.

## Bugs found and fixed
- New order: cylinder dropdown crashed on an empty selection (shared `LpgDropdownField`, with tests).
- Send out: "Load and send out" did nothing unless the godown was re-picked (submit read an unset field).
- Send out: busy drivers/vans came from this branch's trips only; a driver on another branch's trip looked free and the server refused.
- Send out: the load sheet ignored the other orders already on the chosen trip, so a shortage showed as an unexplained server error.
- Booked orders showed a total of Rs 0.00 instead of "priced on confirmation".

## Complaints (2026-10-30)
Tried on the emulator: list with overdue deadlines in red, detail, assign to a staff member (status moved to Assigned, history recorded) and resolve with an outcome and note (status Resolved, outcome card shown). Not tried: Reassign, the Compensated and Rejected outcomes, Call, the per-customer list from a customer page, and raising a complaint on a customer's behalf (not built).

## Cash book (2026-10-30)
Built on the existing cash-book and cash-in-hand endpoints (no backend change). Tried on the emulator: today and the previous day (Rs 905.50 collected, one handover Rs 0.50 short, accepted Rs 905.00), cash with the driver (Rs 2,716.50), the "Still to check" row opening Approvals. Amounts are shown to the paisa, not rounded, so a Rs 0.50 shortfall is not hidden. Not tried: the date-picker dialog (tap the date), a day with disputed handovers.

## Customers and Invoices (2026-10-30)
Built and tried on the emulator against the local backend: customer list and detail, filtered invoice list, invoice detail with the CGST/SGST split, and a cash payment of the Rs 45.28 balance that moved INV-2026-000013 from Partially paid to Paid. This also gives the office the way to settle the GST remainder behind the invoice-total finding below.
Not tried on the emulator: UPI QR sheet, cheque/bank-transfer payments, "Send reminder", and Call. Cylinders-held shows a quiet note for roles without `ledger:read`.

## Look and feel (2026-10-29, later)
- Shared animated gradient splash (`LpgSplash`) in all three apps; native Android launch background and Android 12 splash in brand navy; adaptive icon rescaled so Android's circular mask no longer clips the badge. Checked on the emulator for the Admin app; Customer and Driver use the same widget and built cleanly but were not looked at.
- Admin Orders list, Dispatch queue, search results and trip cards now use the Customer app's "Recent orders" row style (status icon, number, customer and status, amount and date), with a staggered entrance.
- This branch also carries PR #76 (Godown wording, rounded bell chip, cash book date picker), which the Admin work had been branched without.

## Open findings (not fixed)
- Order detail, trip detail and the fleet screens still use the older card layouts.
- Add driver / Add van: the submit button sits under the gesture bar after the keyboard closes; reachable only via the keyboard's Enter key.
- Invoice total (Rs 950.78, with 5% GST) is higher than the Rs 905.50 shown to the customer and collected by the driver, so a fully paid order is "partially paid" (pricing basis decision; see the compliance audit TAX findings).
- Driver cash screen says "Matches the expected" for a count that is Rs 0.50 short.
- Driver app: Today does not refresh after the last delivery (cash card appears only after a restart) and keeps the "Check your van load" card after the load is confirmed.
- Customer app showed a stale "Booked" order after being backgrounded; all three apps log an unhandled WebSocketChannelException when the socket drops.
- Admin order screen has no payment, invoice or proof-of-delivery view (Wave 1 B2).
- Local dev DB was one migration behind (applied); it also holds stale trips that hold the only seeded van.
