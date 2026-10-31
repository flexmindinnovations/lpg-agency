# How an agency's Razorpay keys and secrets are handled

Short answer: they are never shown publicly or to other users. After saving,
nobody - including the agency admin - can read the key secret or webhook secret
back; the page shows only a masked key id (`rzp_live_••••••1234`), the mode
(test or live) and "secret is set" flags.

Verified in code (2026-10-31):

| Question | Answer | Evidence |
|----------|--------|----------|
| Returned by any API? | No. Responses carry a masked key id and booleans only; request secrets are `SecretStr`. The `StoredPaymentCredentials` dataclass is documented never to be serialised | `schemas/payment_gateway.py`, `routers/payment_gateway.py`, `application/accounting/payment_credentials.py` |
| Stored in plain text? | No. Fernet (AES + HMAC) ciphertext in `accounting.payment_gateway_credential`; the key is `LPG_KYC_ENCRYPTION_KEY` in the server env, not in the database | `infrastructure/payments`, `field_encryption.py` |
| In logs? | No. The Razorpay client logs path, status and Razorpay's error description only; secrets are not passed to the logger | `infrastructure/payments/razorpay.py` |
| In error messages? | No. Gateway errors say "Razorpay returned HTTP n: description" or the exception class name; the 422 validation handler returns field messages, never the submitted value | `razorpay.py`, `middleware/problem_details.py` |
| In the audit log? | No. The audit hook writes `[redacted]` for `*_encrypted` columns (and, since this audit, for `webhook_token`, `password_hash`, `token_hash`); it records that a secret changed, never its value | `persistence/audit.py` |
| In backups? | Only as ciphertext. A database dump contains the Fernet ciphertext, which is useless without the server `.env` key. Keep the `.env` backup separate from database dumps | `DEPLOY.md` backup section |
| Who can change them? | Only users holding `tenant:configure` (agency admins) for their own agency; row-level security keeps each agency to its own row | `routers/payment_gateway.py` |
| Another agency's payments | A webhook signed with one agency's secret cannot settle another agency's payment (tenant in the event must match the per-agency URL) | `routers/online_payment.py` |

Remaining caveats:

- The webhook URL contains an unguessable token; anyone who sees it can send
  requests to it, but each request is still rejected unless it carries a valid
  signature. The admin can rotate it (Settings > Online Payments).
- The same Fernet key protects KYC references and Razorpay secrets. There is no
  key-rotation tool yet; losing the key means agencies must re-enter secrets.
- The secrets pass through the server's memory in plain text when a payment
  link is created (unavoidable), and over TLS when first typed in.
- Use Razorpay's restricted keys where possible and never paste secrets in chat.
