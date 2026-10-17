# Tasks: Online Payments (Razorpay)

- [x] T1 `OnlinePayment` aggregate + migration `a9e4c7b2d1f6` + repository
- [x] T2 `PaymentGateway` port + Razorpay adapter (payment links, fetch, webhook HMAC)
- [x] T3 Create / list / refresh / webhook use cases and API
- [x] T4 Apply prepayments when the invoice is generated at delivery
- [x] T5 Settings, env examples, test-key guard in production
- [x] T6 Unit + integration tests
- [x] T7 Customer App "Pay Online" on order and invoice detail screens
- [x] T8 ADR-052, PLAN/STATUS

## Follow-ups (not started, need a decision or another feature)

- [ ] F1 Test against real Razorpay test keys and a public webhook URL (needs the keys from the product owner)
- [ ] F2 Show "Prepaid" on the dashboard order view and the Driver App so drivers do not collect cash twice
- [ ] F3 Refund the excess when a prepaid order is short-delivered (logged as `online_payment_excess_needs_refund` today)
- [ ] F4 Per-agency Razorpay accounts (separate keys or Razorpay Route), if each agency must receive its own money
- [ ] F5 Dashboard "Send payment link" action for staff
