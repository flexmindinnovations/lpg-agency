# Plan: Online Payments (Razorpay)

Requested 2026-10-17 by the product owner. Decision record: ADR-052.

## Goal

Customers, staff and the WhatsApp assistant can collect payment for an order online through Razorpay, before delivery (prepayment, `docs/engineering/payment-flow.md` Path A) or against the order's invoice afterwards, and the money lands on the invoice as an `online_gateway` payment.

## Design

- **Mechanism:** Razorpay Payment Links (hosted checkout URL). One URL serves the app, staff and WhatsApp.
- **Domain:** new `OnlinePayment` aggregate in the accounting context (`created -> paid | expired | cancelled`, then applied to the invoice).
- **Amount:** invoice outstanding if invoiced; otherwise confirmed order total + GST at the tenant's current rate, minus anything already paid online. Open links are reused for the same amount.
- **Confirmation:** signed webhook (tenant taken from the link's notes, then RLS-scoped) plus an explicit refresh endpoint that asks Razorpay.
- **Invoice generation** applies paid, unapplied prepayments to the new invoice.

## API

| Method | Path | Permission |
|---|---|---|
| POST | `/api/v1/orders/{order_id}/payment-links` | `payments:create` |
| GET | `/api/v1/orders/{order_id}/online-payments` | `orders:read` |
| POST | `/api/v1/online-payments/{id}/refresh` | `payments:create` |
| POST | `/api/v1/payments/razorpay/webhook` | none (HMAC signature) |

Customers are scoped to their own orders, dispatchers/managers to their branch (404 otherwise).

## Database

Migration `a9e4c7b2d1f6`: `accounting.online_payment` (RLS, `SELECT/INSERT/UPDATE` for the app role, no `DELETE`), permission `payments:create` for `customer`, `super_admin`, `agency_admin`, `manager`, `accountant`, `dispatcher`.

## Configuration

`LPG_PAYMENTS_PROVIDER`, `LPG_RAZORPAY_KEY_ID`, `LPG_RAZORPAY_KEY_SECRET`, `LPG_RAZORPAY_WEBHOOK_SECRET`, optional `LPG_PAYMENT_LINK_CALLBACK_URL`, `LPG_PAYMENT_LINK_TTL_MINUTES` (default 1440). Without keys the endpoints return 503.

## UI

Customer App: a "Pay Online" section on the order detail (prepayable statuses) and invoice detail (balance due) screens, built only from design-system components. Opens the link in the browser and re-checks status when the app resumes.

## Reuse by other features

The WhatsApp assistant should call `CreateOrderPaymentLinkUseCase` (or the POST endpoint) and send `payment_url`; confirmation needs nothing extra.

## Testing

Unit: aggregate, use cases, invoice application, Razorpay adapter (mock transport, signature checks). Integration: full flow against PostgreSQL with the gateway stubbed, including cross-tenant webhook and RBAC.
