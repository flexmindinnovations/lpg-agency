# 51 — Payment setup: verification, UPI app marks, required setup step

## Why
The Payments settings page (ADR-066) accepts any well-formed IFSC and UPI ID, so a typo only shows up
when a customer's payment fails. It also looks plain next to the UPI apps customers actually use, the
Home setup checklist lets an agency finish without saying how customers pay, and the notification bell's
count chip floats away from the bell.

## Scope
1. **UPI app marks** — GPay, PhonePe, Paytm and BHIM tiles in the UPI card (shared UI component).
2. **UPI ID validation** — format (already) plus a known-PSP-handle check, reported by a verify endpoint.
3. **Bank verification** — IFSC is looked up in the public Razorpay IFSC directory: a code that no
   branch holds is refused on save, a verified one fills bank and branch. A second "confirm account
   number" entry guards against typos. If the directory is unreachable the save is NOT blocked.
4. **Setup checklist** — new required step `payments` (UPI ID or bank account saved).
5. **Bell badge** — count chip sits on the bell's corner instead of floating off the button.

## Not in scope (needs a paid PSP API)
Confirming that the UPI ID or account number exists and who owns it (VPA name lookup, penny-drop).
The verify response is explicit about what was and was not checked. Recorded in TASKS.md.

## Affected
- Backend: `application/accounting/payment_verification.py`, `payment_profile` router/schemas,
  `tenant/setup_progress.py`, `infrastructure/payments/ifsc_directory.py`, OpenAPI export.
- Frontend: `shared/ui` (`UpiAppsComponent`), `shared/data-access` (service + generated client),
  dashboard `payment-settings`, `setup-checklist`, `notification-bell.css`.
- No database change (profile stays a tenant-configuration value).
