# Plan: Driver App Two-Step Sign-In (Password, then OTP)

## Goal

A driver signs in with email and password. If those are correct the backend issues a one-time code, and the driver types it in a second step. Until an SMS provider exists (Phase 14) the code is shown on the same screen. The screen must need no change when real SMS delivery arrives.

## Before

The Driver App used phone OTP only (Agency Code + phone). `POST /auth/login` (email + password) works for a driver account but returns tokens straight away, so it is a one-factor path.

## Design

- **Step 1 `POST /auth/driver-login`** `{email, password}`: same checks as `LoginUseCase` (generic error, lockout, active account) plus role must be `driver`, a phone number must be on file, and the agency must not be suspended or lacking an active licence. It issues **no tokens**. It issues an OTP and returns `{phone_hint, dev_otp}`.
- **Step 2 `POST /auth/driver-login/verify`** `{email, code}`: redeems the OTP for tokens, with the same agency/licence checks as step 1.
- **Why no challenge id:** the step-1 OTP is stored under a key only step 1 writes (`tenant:{tid}:driver-login-otp:{user_id}`), so a valid code proves the password step passed. This key differs from the customer/driver phone-OTP key, so neither flow can satisfy the other.
- **Dev OTP:** `dev_otp` is filled only when `Settings.otp_delivery_dev_mode` is on. `Settings` already refuses that flag outside `environment=local`. It is `null` everywhere else, and the app shows its banner only when the field is non-null.
- Both endpoints are rate limited (10/min). Verify had no attempt limit before; this adds one for the new path.
- The existing `/auth/otp/*` endpoints are unchanged (the Customer App still uses them).

## Decisions taken without being asked (reversible)

1. "Username" means the account **email**. Drivers have no separate username field.
2. The old phone-OTP login screen in the Driver App is replaced, not kept alongside.
3. A driver account without a password or phone number cannot sign in this way.

## Out of scope / deferred

- How a real driver gets a password (the seed script sets one; the onboarding flow does not). See ADR-050.
- Real SMS delivery (Phase 14).
- Regenerating the Angular client from the new OpenAPI paths.
- Integration test against real PostgreSQL/Redis.
