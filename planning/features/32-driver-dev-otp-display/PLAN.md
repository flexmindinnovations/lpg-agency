# Plan: Show the Login OTP on the Driver App Screen (Testing Only)

## Goal

No SMS/WhatsApp gateway exists yet (Phase 14), so a tester cannot see the OTP the Driver App login asks for. Show the code on the login screen so testers can sign in smoothly, then remove it when a gateway is integrated.

## Design

The login flow stays exactly as designed: Agency Code + Phone number, `POST /auth/otp/request`, then `POST /auth/otp/verify` (`docs/data/11-api-contracts.md`, ADR-035). Nothing in the backend changes.

- After a successful OTP request the Driver App calls the existing dev route `GET /api/v1/dev/otp-inbox/{phone}`. `LoggingOtpDelivery` already stashes the code there, and `api/app.py` registers the route only when `not settings.is_production`.
- If the call returns a code, the screen shows it in a "Testing only" banner above the code field. If it fails (404 in production) or returns nothing, there is no banner.
- The app only makes the call when `SHOW_DEV_OTP` is true. It defaults to true in debug builds and false in release builds (`--dart-define=SHOW_DEV_OTP=true|false` overrides it).

## Removing it later

Delete `dev_otp_provider.dart`, the `_DevOtpBanner` and the lookup call in `login_screen.dart`, and `AuthApi.fetchDevOtp`.

## Out of scope

- The Customer App login (same pattern would work; not requested).
- Any change to the backend, the OTP contract, or the dev route.
