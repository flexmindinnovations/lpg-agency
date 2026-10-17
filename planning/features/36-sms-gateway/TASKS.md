# Tasks: SMS Gateway (OTP + Order Updates)

- [x] 1. `SmsTemplate`, template-aware `SmsChannel`, `SmsDeliveryError`; OTP `purpose`
- [x] 2. `Msg91SmsChannel` + `build_sms_channel`; settings
- [x] 3. `SmsOtpDelivery`; `get_otp_delivery` selects it when a provider is set
- [x] 4. Notification job sends order SMS by template; API lifespan + worker own one channel each
- [x] 5. Delivery OTP is best-effort in `DepartOrderUseCase`
- [x] 6. Unit tests; integration test doubles updated
- [x] 7. ADR-054, `.env.example`, production compose env, MODULE_STATUS row
- [ ] 8. Register DLT entity, sender header and the five templates; create MSG91 templates (product owner)
- [ ] 9. Set the env vars on UAT/production and send one real SMS per template

## Deferred

- Per-agency sender ID / DLT entity (today one platform-wide sender serves every tenant).
- A "resend delivery OTP" endpoint for when the departure SMS fails.
- A second provider adapter (Twilio or Gupshup), only if MSG91 is replaced.
- Delivery reports (MSG91 webhook) written back to `notification_log`.
