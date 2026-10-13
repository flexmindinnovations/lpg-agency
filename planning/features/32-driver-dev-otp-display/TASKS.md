# Tasks: Driver Login Dev OTP Display

- [x] 1. `AuthApi.fetchDevOtp` (reads `/dev/otp-inbox/{phone}`) + 2 tests
- [x] 2. `dev_otp_provider.dart`: `showDevOtp` flag, `devOtpLookupProvider`
- [x] 3. Login screen: look up the code after a successful request, show a "Testing only" banner + 2 widget tests
- [x] 4. ADR-050
- [ ] 5. Run on the emulator against the local backend (needs the developer's machine)

## Deferred / removal

- When an SMS/WhatsApp gateway lands: delete the dev OTP code listed in PLAN.md.
- Customer App login could show the code the same way if wanted.
