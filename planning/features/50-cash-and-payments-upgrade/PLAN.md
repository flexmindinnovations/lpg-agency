# 50 - Cash handover and payments upgrade

**Why:** Cash handover was a single number (declared vs expected). Agencies need the controls a cash business expects: where money is banked, how customers can pay by UPI, what a driver is carrying, a counted-by-note handover with a reason for any difference, and a daily cash book. Invoices should carry the bank/UPI details and a pay QR. Razorpay must be demoable before real keys exist.

## Scope (ADR-066)
1. **Payment profile** (Admin > Settings): bank account (holder, bank, account no., IFSC, branch), UPI ID and payee name, invoice footer note. Stored as tenant configuration (`payment_profile`), validated (IFSC, VPA, account digits). Read for printing by any staff role; written by admin.
2. **UPI pay QR**: `GET /payments/upi-qr?order_id=|invoice_id=` returns the `upi://pay` link and a PNG QR for the outstanding amount. Used by dashboard, driver app (customer pays at the door), customer app and the invoice.
3. **Invoices**: new A4 layout (header band, GST breakup, amount in words, bank + UPI + QR block, footer note) and thermal layout with the UPI line.
4. **Razorpay with dummy config**: `LPG_PAYMENTS_PROVIDER=mock` is a gateway that needs no keys: it creates a local link, and `POST /online-payments/{id}/simulate-paid` (mock only, staff) marks it paid. Real Razorpay is unchanged; keys arrive later through env vars.
5. **Cash controls**:
   - Handover declaration gains optional `denominations` (count per note), `variance_reason` (required when short or excess), and `upi_collected` shown beside cash for the day (mode split).
   - Driver **cash in hand**: `GET /cash-handovers/cash-in-hand` lists, per driver, cash collected on routes not yet handed over.
   - **Cash book**: `GET /cash-handovers/cash-book?date=` gives collected by mode (cash/UPI/online), handed over, accepted, disputed, short/excess for the day.
   - Review (accept/dispute) already exists; segregation of duties stays.
6. **Surfaces**: dashboard (Settings > Payment profile, handover register shows denominations/variance, Cash book page, invoice drawer QR), driver app (denomination count at handover, reason, UPI QR on the record-delivery screen, cash in hand on Today), customer app (pay by UPI QR / link on invoice), admin app (payment profile read-only view, cash book, handover review shows denominations).

## Compatibility
All API changes are additive. Existing declare/review payloads keep working; new fields are optional. The admin-app thread's trip-detail work keeps using `/cash-handovers/*` unchanged.

## Out of scope for now
Bank statement reconciliation, direct UPI collect requests (needs a PSP), refunds, cash deposit slips to bank.
