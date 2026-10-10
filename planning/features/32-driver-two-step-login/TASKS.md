# Tasks: Driver App Two-Step Sign-In

- [x] 1. `application/identity/driver_login.py`: `StartDriverLoginUseCase`, `VerifyDriverLoginUseCase`
- [x] 2. Schemas and routes `POST /auth/driver-login`, `POST /auth/driver-login/verify`; dev-only `dev_otp`
- [x] 3. 15 unit tests (password, lockout, role, licence, OTP reuse, bypass attempt)
- [x] 4. OpenAPI spec regenerated
- [x] 5. `AuthApi`, `AuthRepository`, `AuthController`: `startDriverLogin` / `verifyDriverLogin`
- [x] 6. Driver `LoginScreen`: email + password, then code with on-screen dev OTP
- [x] 7. Dart tests: repository, login screen, existing fakes updated
- [x] 8. `.claude/backend-dev.bat` sets `LPG_OTP_DELIVERY_DEV_MODE=true`
- [x] 9. ADR-050, this plan
- [ ] 10. Run on the emulator against the local backend (needs the developer's machine)
- [ ] 11. Integration test against real PostgreSQL/Redis (HTTP flow end to end)

## Deferred

- Regenerate the Angular client (`frontend/libs/shared/data-access/.../generated`) from the new OpenAPI paths
- Decide how drivers are given a password when an agency adds them
- Real SMS delivery, then drop `dev_otp` handling if wanted (the app already hides the banner when it is null)
- Attempt limit that invalidates the OTP after N wrong codes (today: rate limit only)
