# Tasks: Customer App Login on First OTP Sign-in

- [x] 1. `Customer.can_get_app_login` + unit tests
- [x] 2. `CustomerLoginProvisioner` port; `VerifyOtpUseCase` provisions when no login exists
- [x] 3. `SqlAlchemyCustomerLoginProvisioner`; shared `insert_identity_user`
- [x] 4. Wire into `/auth/otp/verify`; import-linter ignore entries
- [x] 5. Integration tests (create + link, reuse, ineligible statuses, other tenant)
- [x] 6. ADR-051, MODULE_STATUS row, customer_app README testing steps
- [ ] 7. Sign in on a phone against UAT after deploy (needs the product owner)

## Deferred

- Dashboard indicator showing whether a customer has an app login yet.
