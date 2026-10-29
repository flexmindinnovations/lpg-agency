# Tasks

- [x] Backend: verification module (UPI handle check, IFSC directory port + Razorpay IFSC adapter)
- [x] Backend: `POST /payment-profile/verify`; save refuses an IFSC no branch holds
- [x] Backend: `payments` setup step
- [x] OpenAPI + Angular client (spec merged by hand: the local Pydantic version differs from CI's, so a fresh export adds unrelated churn)
- [x] Shared UI: `UpiAppsComponent`
- [x] Dashboard: payment settings — logos, verify IFSC/UPI, confirm account number
- [x] Dashboard: setup checklist `payments` step
- [x] Dashboard: notification bell badge — on the glyph's corner, fully rounded
- [x] Dashboard: cash book date picker matches the other pickers (icon inside the input, global date format)
- [x] Dashboard: "Warehouse" -> "Godown" in user-visible text; glossary section added
- [x] Docs: ADR-066 amendment, STATUS
- [x] Admin app: run on emulator

## Discovered / deferred
- [ ] Holder-name verification (VPA lookup) and account penny-drop — needs a PSP account (Razorpay/RazorpayX).
- [ ] Replace the drawn UPI app marks with the official brand assets once they are licensed for use.
- [ ] Godown wording in the Customer/Driver/Admin mobile apps, backend messages and printed documents.
- [ ] Product-owner sign-off on further wording: Consumer, Stock, Cash Memo, Delivery Staff (see `docs/business/glossary.md`).
- [ ] `export_openapi --check` could not be run locally (Pydantic version differs); CI will confirm the merged spec.
