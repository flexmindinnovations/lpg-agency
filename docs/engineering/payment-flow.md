# Workflow: Payment Flow

## 1. Overview
Describes how payment is captured, recorded, and reconciled across the two payment paths the blueprint identifies: online prepayment (Customer App) and Cash-on-Delivery collection (Driver App: Cash/UPI/Card).

## 2. Actors
Customer, Delivery Driver, Accountant/Cashier, Payment Gateway (external), System.

## 3. Path A — Online Prepayment (at Booking Time)

> **Implemented 2026-10-17 (ADR-053)** with Razorpay payment links. Prepayment is possible once the order is confirmed (prices fixed) and is held as an `OnlinePayment`, then applied to the invoice generated at delivery — the "advance against the invoice" option recommended in the gap below.

> **Per-agency accounts (ADR-067, 2026-10-31).** Each agency saves its own Razorpay key id, key secret and webhook secret in Settings > Online Payments; payment links, refresh and the WhatsApp assistant use that agency's account, falling back to the platform-wide `LPG_RAZORPAY_*` keys (or the demo gateway) when none is saved. Each agency registers its own webhook URL, `/api/v1/payments/razorpay/webhook/{token}` (shown on that page), verified with that agency's webhook secret.

1. Customer selects "Pay Online" during booking (`workflows/customer-booking.md` step 6).
2. System redirects to/invokes the integrated Payment Gateway.
3. Customer completes payment via the gateway's supported methods.
4. Gateway returns a success/failure callback to the system.
5. On success: Order is marked Prepaid; system generates a payment record linked to the (not-yet-existing) invoice, or holds it as an advance against the order.
6. On failure: Order remains in Pending with payment status Unpaid; customer is prompted to retry or switch to Pay on Delivery.

**Gap:** The exact invoice-timing relationship (is the invoice generated at booking time for prepaid orders, or only at delivery like COD orders?) is not defined in the blueprint. Recommended: invoice is always generated at delivery (to correctly reflect final delivered quantity/price), with prepayment treated as an advance/credit applied against that invoice. **Needs business confirmation.**

## 4. Path B — Cash on Delivery (COD)

1. At the Delivery Confirmation step (`workflows/delivery-flow.md` step 9f), driver records payment method and amount collected.
2. For Cash: amount is added to the driver's shift cash-in-hand total.
3. For UPI/Card: payment is processed via a device-integrated payment method (specific integration mechanism not defined in blueprint — likely a mobile POS/UPI QR flow — Open Question).
4. System generates the Invoice at this point (per BR-17) with payment status Paid (or Partially Paid if a split payment is later supported).
5. Invoice is downloadable by the customer (Customer App feature, explicit in blueprint).

## 5. Path C — End-of-Shift Cash Reconciliation

1. At shift end, driver's total recorded cash collections for the day are computed by the system.
2. Driver hands over physical cash to the Accountant/Cashier.
3. Cashier confirms received amount in the system; a CashHandover record is created.
4. Any variance between expected (system-recorded) and actual (handed-over) cash is flagged (ties to `modules/accounting.md` §3.4).

## 6. Path D — Outstanding Balance Handling

1. If a customer's order is delivered without full payment (e.g., driver allows partial/deferred payment — **policy not defined in blueprint**), the invoice remains Partially Paid/Unpaid.
2. Outstanding balance accrues against the customer (`modules/accounting.md` §3.3).
3. Future bookings are checked against this balance per BR-19.
4. Collection follow-up process (calls, reminders, credit hold) is **not defined in the blueprint** — Open Question.

## 7. Exception Flows
- **E1 — Online payment succeeds but order creation fails** (e.g., stock became unavailable between payment and confirmation): Requires an automatic refund or credit-note process — **not addressed in blueprint.**
- **E2 — Driver's device has no connectivity for UPI/Card processing at delivery point**: Needs a documented fallback (e.g., default to cash, or mark as "collect later").
- **E3 — Refund request after delivery** (customer dispute, overcharge): No refund workflow defined (see `modules/accounting.md` §3.7 gap).

## 8. Related Business Rules
BR-17, BR-18, BR-19, BR-20.

## 9. Related Modules
`modules/accounting.md`, `modules/order-management.md`, `modules/delivery-management.md`.

## 10. Open Items
See `questions/open-questions.md` Q-08, Q-09, Q-31 (UPI/Card device integration model), Q-32 (deferred/partial payment policy), Q-33 (collections process).

## 11. Which payment methods are offered
The apps do not carry their own list. `GET /payments/methods` returns what the agency's set-up allows, in three places: `booking` (a customer's preference), `delivery` (recorded at the door by the driver or the office) and `office` (recorded against an invoice). Cash is always offered; UPI needs a UPI ID on the payment profile; online payment needs the agency's Razorpay account connected (ADR-067); bank transfer needs bank details; on credit needs a credit limit; cheque is an office-only record. Card is not offered. Rules live in `application/accounting/payment_methods.py`.

