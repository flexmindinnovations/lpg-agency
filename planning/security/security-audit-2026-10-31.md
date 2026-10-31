# Security audit and hardening - 2026-10-31

Scope: backend API, dashboard, mobile apps, CI/CD and the single-droplet deploy.
Method: code review of auth, authorization, payments, uploads, headers, config,
CI and deploy files; `pip-audit` and `npm audit`; secret-pattern scan of the
tree. Not done: a live penetration test, and nothing could be checked on the
production server itself (this environment cannot reach it or SSH to it).
Standards used as the checklist: OWASP ASVS 4, OWASP API Security Top 10 (2023),
PCI-DSS-minded handling of card-adjacent data, India DPDP Act basics.

Fix status: **Fixed** = merged to main in this audit. **User action** = needs
the owner. **Open** = recommended, not done yet.

## Findings

| # | Severity | Finding | Evidence | Status |
|---|----------|---------|----------|--------|
| 1 | High | Login/delivery OTP could be brute-forced: `/auth/otp/verify` had no attempt cap or rate limit; a wrong code left the code valid for its whole TTL (5 min login, 24 h delivery) | `infrastructure/identity/otp_service.py`, `routers/auth.py` | Fixed: 5 wrong codes destroy the code; verify throttled per IP and per phone |
| 2 | High | Per-IP rate limits saw only the Caddy container IP, so all users shared one bucket (login 10/min for everyone, trivially exhausted by one attacker) | `gunicorn.conf.py`, `dependencies/identity.py` | Fixed: gunicorn trusts Caddy's `X-Forwarded-For` (backend port is not published) |
| 3 | High | Cross-tenant file access (BOLA): `blob_ref` strings from clients were passed to storage `download`/`url` with no tenant check, so one agency could OCR or get a signed URL for another agency's KYC/POD files if it knew a key | `customer/use_cases.py`, `delivery/compliance_use_cases.py`, `routers/*` | Fixed: API storage is limited to `tenant/{id}/`; foreign keys answer 404 |
| 4 | High | Possible live OTP exposure: in `uat` the unauthenticated `/api/v1/dev/otp-inbox/{phone}` returns any pending OTP for any tenant. The deploy compose file allows `LPG_ENVIRONMENT=uat` and the apps ship with `SHOW_DEV_OTP` | `routers/dev_tools.py`, `docker-compose.prod.yml`, DEPLOY.md | **User action**: confirm production runs `LPG_ENVIRONMENT=production`; never run `uat` with real customers. Cannot be verified from here |
| 5 | Medium | OTP codes were written to application logs in production when no SMS provider is set | `otp_delivery.py` `LoggingOtpDelivery` | Fixed: never logged in production (login by OTP then needs `LPG_SMS_PROVIDER` set) |
| 6 | Medium | Uploads: no size limit, no type check, client file name placed in storage key | `routers/documents.py`, `customer.py`, `order.py` | Fixed: 10 MB cap, image/PDF allowlist, sanitised names; Caddy refuses bodies over 12 MB |
| 7 | Medium | No security response headers (HSTS, nosniff, framing) on API or dashboard | `api/app.py`, `frontend/Caddyfile` | Fixed (API + Caddy). Full script CSP is Open, see below |
| 8 | Medium | Dependencies with known CVEs: 103 Python advisories (pypdf, aiohttp, pillow, urllib3, werkzeug, ...) and 6 npm (DOMPurify critical, @angular/router, zod) | `pip-audit`, `npm audit` | Fixed by lock upgrades; unit tests pass |
| 9 | Medium | Audit log could record credential-bearing columns (`password_hash`, `token_hash`, `webhook_token`) for rows changed through a Unit of Work | `persistence/audit.py` | Fixed: redacted like `*_encrypted` |
| 10 | Low | Client-supplied `X-Correlation-ID` echoed/logged unvalidated | `middleware/correlation.py` | Fixed: only `[A-Za-z0-9._:-]{1,64}` accepted |
| 11 | Low | `/auth/refresh` and `/auth/password/reset` had no rate limit | `routers/auth.py` | Fixed |
| 12 | Low | `dump.rdb` (Redis dump) and an `actionlint` tarball committed at repo root | git ls-files | Fixed: removed and ignored. The dump held only rate-limit and tenant-status keys |
| 13 | Low | Locked-account login returns a different message than a wrong password (account enumeration) | `application/identity/login.py` | Open |
| 14 | Low | Rate limiter fails open when Redis is down (documented choice) | `limiter.py` | Open (acceptable; alert on Redis down) |
| 15 | Low | GitHub Actions pinned to tags (`@v4`), not commit SHAs | `.github/workflows/*` | Open (Dependabot can keep SHAs fresh) |
| 16 | Info | Razorpay and Firebase client keys: Firebase `AIza...` keys in `google-services.json` are public by design but should be restricted | mobile apps | **User action**: restrict the key to the apps' package names and SHA-1 in Google Cloud console |

## Deploy and operations (not changeable from code)

- **Backups (Open, important):** the only documented backup is a manual `pg_dump` to `/opt/backups` on the same droplet, unencrypted. Enable DigitalOcean droplet backups and/or a nightly encrypted dump copied off the server. The dump contains PII and the encrypted Razorpay secrets; the Fernet key lives only in the server `.env`, so keep that file backed up separately from the dump.
- **SSH:** root login by key only (good). Recommended: disable password auth explicitly, add `fail2ban`, use a non-root deploy user.
- **Network:** only ports 80/443 are published; Postgres and Redis stay on the internal compose network; Redis has a password; firewall `ufw` is enabled per DEPLOY.md.
- **Containers:** backend runs as non-root `app`; images pinned by digest.
- **TLS:** automatic Let's Encrypt when `SITE_ADDRESS` is a domain; HSTS now sent.
- **Content-Security-Policy (Open):** only non-breaking directives are enforced (`frame-ancestors`, `base-uri`, `object-src`, `form-action`). A `script-src 'self'` policy needs the production build's inline critical-CSS loader removed (set `inlineCritical: false`) and a test pass; plan it as a separate change.

## Verified as sound (no change needed)

- **Passwords:** Argon2id (OWASP parameters), 12-character minimum, lockout after 5 failures for 15 min.
- **Tokens:** RS256 pinned (`algorithms=["RS256"]`), 15-minute access token, refresh token rotation with reuse detection that revokes all of the user's tokens, HttpOnly/Secure/SameSite=Strict cookie, tokens stored hashed. Mobile apps use `flutter_secure_storage`.
- **Authorization:** tenant isolation by PostgreSQL row-level security with a non-superuser app role plus tenant-scoped repositories; permission checks per route; WebSocket subscriptions are server-constructed channels with an ownership check for `order:{id}` (the earlier gap is closed).
- **Config:** production refuses wildcard CORS, debug, dev OTP mode, mock payments and Razorpay test keys unless explicitly allowed; API docs are off in production; SQL built with f-strings uses constants only.
- **Webhooks:** HMAC-SHA256 with constant-time compare, empty secret or missing signature rejected, tenant in the event must match the per-agency URL, amounts come from the stored payment (not the webhook body), applying an event twice changes nothing.
- **Validation errors** do not echo submitted input, so a secret typed in a form is not reflected back.

## Razorpay keys and secrets - where they go

See `razorpay-secrets-handling.md` in this folder for the full answer.

## User actions

1. Confirm production's `LPG_ENVIRONMENT` is `production` (not `uat`). With `uat`, anyone can read OTPs.
2. Turn on SMS (`LPG_SMS_PROVIDER=msg91` plus DLT templates) before real customers use OTP login; production no longer logs codes.
3. Rotate the FCM service-account key that was pasted in chat once (Firebase console > Service accounts > generate new key, update `FCM_SERVICE_ACCOUNT_JSON`, delete the old key).
4. Restrict the Firebase/Google API key by app package and SHA-1.
5. Enable automatic droplet backups and an off-server encrypted database dump; back up the server `.env` separately.
6. Enter Razorpay keys only in Settings > Online Payments (never in chat or tickets). Use a restricted-permission Razorpay key where offered.
