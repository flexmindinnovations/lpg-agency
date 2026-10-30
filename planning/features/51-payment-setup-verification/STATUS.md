# Status

Implemented 2026-10-29; awaiting CI. Backend unit tests pass (the only failures are the 7 `test_anthropic_adapter` tests, which fail locally because the `anthropic` package is not installed). Verified in the dashboard against the live IFSC directory: a real code fills bank and branch, an unknown code is refused, a UPI ID reports its issuing app, a changed account number asks for confirmation.

Honest limits: the UPI check covers format and issuing handle only. It cannot say the ID exists or whose it is; that needs a payment-provider account. The UI says so.
