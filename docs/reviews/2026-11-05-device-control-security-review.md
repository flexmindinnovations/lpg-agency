# Security review: device registration and access control (ADR-071)

**Date:** 2026-11-05 · **Scope:** story 11.10 of `planning/features/61-mobile-ui-revamp/` · **Reviewer:** the engineer who built it (not independent), with adversarial tests written against the code. **This is not a penetration test and no outside party has reviewed it.**

## What was reviewed
Every path a phone, a token or an admin can use: password sign-in, OTP sign-in, refresh, an ordinary request, `GET /devices/me`, the realtime WebSocket, the admin API (`/admin/license/devices`), the `device_control` setting, the new database function that revokes a phone's refresh tokens, the cache, the audit trail, the admin alert and the block push, and the mobile apps' handling of refusals and of queued deliveries.

## How it was tested
- `tests/unit/test_application_device_access.py`: the binder and the request gate over mode × who signs in × the phone's state.
- `tests/integration/test_device_enforcement_api.py` and `test_device_enforcement_matrix.py` (real ASGI stack, PostgreSQL as the non-superuser role, Redis): every phone state (unknown, pending, approved, blocked, removed) against sign-in, an existing session's request, refresh and `GET /devices/me`; OTP sign-in; seat limit; two agencies; a token moved to another phone; racing first sign-ins; one login flooding the queue; a block that must not touch the user's other phone; and the realtime connection over a real socket (pending, wrong phone, blocked, and a chatty client).
- Raw-SQL row-level-security checks on `platform.linked_device` (`test_linked_devices_api.py`).
- Mutation checks: removing the request gate, the realtime re-check and the queue cap each made the matching tests fail.

## Findings fixed in this change
| # | Finding | Severity | Fix |
|---|---|---|---|
| F1 | The realtime connection re-checked the phone only when the client went quiet for 30 s. A client that sent a frame more often than that was never re-checked, so a blocked phone could keep its live feed. | Medium | Re-check on a timer (`_DEVICE_RECHECK_S`, 30 s) on every pass of the receive loop. Tested over a real socket with a client that sends every 100 ms. |
| F2 | Any valid login could register unlimited new phones by sending different install IDs. Each raised a pending entry and an alert for the agency admin. | Low–medium | At most 5 phones waiting per login (`DEVICE_QUEUE_FULL`, 409). A phone already waiting can still sign in. Observe mode is not limited (those phones are approved). |
| F3 | A lint failure (`E501`) left in the enforcement branch after a late edit. Not a security issue; noted because CI would have failed. | Process | Fixed, and every branch re-checked. |

## Residual risks (accepted or open; please read)
| # | Risk | Why it remains | What reduces it |
|---|---|---|---|
| R1 | **Device control stops a phone, not a credential.** A staff password used with no app headers is a dashboard-style session and is not checked. The Admin app is only recognised by the `X-App-Type: admin_app` header it sends at sign-in. | The web dashboard has no device and shares the login. Closing it would break the dashboard. | Remove or deactivate the person's login (existing user management). Say so in the admin guide. |
| R2 | A driver's token is always device-checked, but a driver who never reaches enforce-mode agencies (mode `off`/`observe`) is not blocked at all. | By design: that is what lets an agency roll out safely. | The admin chooses the mode; the dashboard says what each mode does. |
| R3 | The install ID is a bearer secret. Someone who steals both the access token and the install ID (for example from a compromised phone) can act as that phone. | There is no hardware-backed attestation. | Block the phone; its refresh tokens are revoked at once. Optional story 11.11 (Play Integrity / App Attest) was left out as agreed. |
| R4 | Cache lag: a phone's status is cached ~30 s and the agency mode ~60 s. An admin action and a mode change clear their own cache at once, but another server process could serve a stale entry until it expires if Redis is shared incorrectly. | Redis is shared by all processes, so the lag is only seen when invalidation itself fails (logged, best-effort). | The TTLs are short; the realtime re-check and every request read the cache, not an old token. |
| R5 | An unreadable or unknown `device_control` value is treated as `off` (fail-open), not `enforce`. | A typo must not lock every driver out. | The API rejects any value other than off/observe/enforce, so an unknown value cannot be stored through it. |
| R6 | `identity.auth_revoke_all_refresh_tokens_for_device(uuid)` is `SECURITY DEFINER` and does not check a tenant. | It follows the existing pre-tenant auth functions (a refresh token's `tenant_id` is NULL by design). The device id is a random UUID the caller must already hold. | Only the application role can execute it; device ids are not exposed across tenants. |
| R7 | The Android ID / iOS vendor ID is personal data. The server stores only its SHA-256; the dashboard shows 8 characters. The apps send it in the sign-in body. | It is needed to recognise a reinstalled phone. | Hashed at rest, never logged, privacy line on the "Name this phone" screen. Whether Google Play policy or India's DPDP Act needs a fuller notice is **unverified**; ask the agency's adviser. A retention period for removed devices is still to be decided. |
| R8 | On iOS the Keychain can keep the install ID after the app is uninstalled, so a reinstalled app may look like the old phone. | Platform behaviour of `flutter_secure_storage`. | An admin can remove the phone; it then asks again. Not tested on a device. |
| R9 | A phone waiting for approval can sign in and hold a session. It can only reach `GET /devices/me`, refresh and logout. | The app needs a session to ask "am I approved yet?". | Every other request is refused with `DEVICE_PENDING`; tested for every state. |
| R10 | The device name is typed by the user and appears in the admin alert and the dashboard. | It must be human readable. | Limited to 60 characters, whitespace-collapsed; the dashboard and notification text are escaped by Angular and plain text in push. |
| R11 | Rate limits are the existing per-IP limits on sign-in and refresh. There is no separate limit on `GET /devices/me`. | It is cheap (cached) and needs a valid session. | Revisit if it shows up in load tests. |

## Checked and found sound
- Tenant isolation: the device row, its cache key (`tenant:{id}:device:{id}`), the lookup (`tenant_id` and `id`) and the refresh-token revoke by device id. Two agencies using the same phone get two records. Raw SQL as the application role cannot read, update or insert another agency's devices.
- The device check happens after the password or OTP is verified, so an unauthenticated caller cannot probe which phones exist.
- Comparison of install-ID hashes uses a constant-time compare. Plain install IDs and hardware IDs are never stored, never put in a notification or realtime message, and never in an audit entry (the IMEI/serial note text is not audited either).
- Blocking is in the database before anything else: the status check reads the database truth if the cache is empty or Redis is down; the post-commit handlers (cache clear, token revoke, realtime, push) log their failures instead of failing the admin's request.
- Sign-in, refresh and request errors carry stable codes; a plain 403 (`PERMISSION_DENIED`) is not mistaken for a device refusal by the mobile apps or the sync queue.
- Offline drivers: a `DEVICE_*` refusal returns a queued delivery to `pending` (no attempt counted, nothing discarded), and a block never wipes local data.

## Not reviewed / not done
- No device or emulator testing (secure storage, the Android ID plugin, real WebSocket close handling on a phone).
- No independent review, no load test of the per-request check, no review of the legal wording.
- The real-phone check in story 11.1 (what IMEI, Android ID and model a normal app can read on the agency's phones) is still open.
