# 57 — Payment methods in the three apps come from the agency's own set-up

## Why
Each app carried its own fixed list of ways to pay (Customer: cash, UPI, card, online; Driver: cash, UPI, card, online, on credit; Admin: cash, UPI, card, on credit at the door, plus cheque and bank transfer for invoices). An agency with no UPI ID still saw UPI, one with no payment gateway still saw "Online", and nobody had set up card at all. The owner's instruction (2026-10-31): all three apps take payment configuration from the agency's payment provider configuration, dynamic, nothing hardcoded.

## Design
- New read endpoint `GET /payments/methods` (any signed-in user, like `GET /payment-profile`). The server works the lists out from what the agency has configured and returns three: `booking` (a customer's preference), `delivery` (what the driver or the office records at the door) and `office` (what is recorded against an invoice).
- Rules (`application/accounting/payment_methods.py`, one place):
  - Cash: always. It needs no provider.
  - UPI: the payment profile holds a UPI ID (the QR is built from it).
  - Online payment: the agency's own Razorpay account is connected (ADR-067).
  - Bank transfer (office only): the payment profile holds bank details.
  - On credit (door only): a credit limit is configured; without one nothing bounds what a customer may take on account.
  - Cheque (office only): always; it needs no provider.
  - Card: not offered. The platform has no card-machine set-up to configure. Existing card payments still display.
- `api_client` gains `PaymentApi.getPaymentMethods()` and `PaymentMethods`. Each app has `paymentMethodsProvider` (auto-disposed, read each time a payment screen opens, no retry). If the read fails the screens fall back to cash only, which is always safe.
- Customer order placement, Driver record delivery, Admin deliver sheet and Admin record payment sheet all read it; the fixed lists are gone.

## Out of scope
- A per-agency switch to turn card or other methods on. Card needs a configuration to hang it on first; noted, not built.
- The Angular dashboard's own method pickers (not asked for).
- Offline: a driver without a connection at the door sees cash only until the list loads. Caching the last list on the device is a possible follow-up.
