# 54 — Per-agency Razorpay credentials (ADR-067)

## Why
Razorpay keys came from server environment variables (feature 35, PR #93), which assumes one Razorpay
account for the whole platform. Every agency has its own account, and agencies cannot edit an env file.

## Scope
1. **Storage** — `accounting.payment_gateway_credential`, one row per tenant: key id (clear), key secret
   and webhook secret (Fernet, `LPG_KYC_ENCRYPTION_KEY`), opaque `webhook_token`. RLS + SECURITY DEFINER
   token -> tenant lookup (migration `e3a7c1d9b5f2`).
2. **API** (`tenant:configure`) — `GET/PUT/DELETE /payment-gateway`, `POST /payment-gateway/rotate-webhook-token`,
   `POST /payment-gateway/test`. Write-only secrets; responses carry masked key id, mode, flags, webhook path.
3. **Resolution** — `get_payment_gateway` (request) and the WhatsApp job pick the agency's key, else the
   platform default (env Razorpay, or the demo gateway).
4. **Webhook** — `POST /payments/razorpay/webhook/{token}` verifies with that agency's webhook secret and
   only applies events for that tenant. The shared URL stays for agencies on the platform account.
5. **Audit** — saves, removals and rotations are audited by the generic hook; `*_encrypted` columns are redacted.
6. **Dashboard** — Settings > Online Payments: keys form, test connection, remove, webhook URL + copy,
   issue a new URL, test/live banner.

## Decisions
- Reuse `LPG_KYC_ENCRYPTION_KEY` rather than add a second key: it is already provisioned and backed up.
- Agency test keys are accepted everywhere (no money moves); the platform key guard from PR #93 is unchanged.
- A blank key id / secret / webhook secret on save keeps the saved value; changing the key id needs a new secret.

## Not in scope
- Razorpay Route / sub-merchant onboarding (platform collecting on behalf of agencies).
- Per-agency refunds API, key rotation reminders, encryption-key rotation tooling.
