# 43 — Post-delivery customer actions — Plan

## Problem (reported 2026-10-19)

1. A delivered order still offered **Cancel Order** in the Customer App.
2. After the driver recorded the payment at delivery, the Customer App still
   offered **Pay Online**.

## Causes

- The driver's doorstep collection (`orders.proof_of_delivery.payment_method`
  / `amount_collected`) was never recorded on the invoice, so a delivery paid
  in cash or UPI left an `issued` invoice with the full balance due. The
  invoice screen offered Pay Online and the server would have created a link
  for money already collected. `payment-flow.md` Path B step 4 says the
  invoice is generated *paid*.
- `orderDetailProvider` and `invoiceDetailProvider` were cached for the whole
  app session (not `autoDispose`) and the detail screens had no pull-to-refresh,
  so an order opened while out for delivery kept showing Cancel and Pay Online
  after it was delivered.
- The Cancel button was hidden by a deny-list that missed `closed` and `draft`.

## Changes

- Backend: `GenerateInvoiceForOrderUseCase` records the doorstep collection as
  an invoice payment after gateway prepayments (cash/UPI/card/online; never
  `credit`; capped at the outstanding balance). New `ProofOfDeliveryReader`
  port, implemented by `SqlAlchemyProofOfDeliveryRepository.get_by_order_id`.
- Backend: `CreateOrderPaymentLinkUseCase` refuses a link when the order's
  invoice is paid, cancelled or refunded.
- Migration `c8d4e2f6a1b3` backfills doorstep payments onto existing
  invoices with the same rule.
- Customer App: detail providers are `autoDispose`, detail screens have
  pull-to-refresh, Cancel is offered only from an allow-list of cancellable
  statuses, and order notifications also refresh the invoice list.
- Server already rejects cancel from `delivered`/`closed` (D-19 state machine);
  the dashboard already gates Cancel by status. No change there.
