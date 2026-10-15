# Plan: Customer App Login on First OTP Sign-in

## Goal

A customer the agency adds on the dashboard has a `customer.customer` row but no `identity.identity_user`, so Customer App OTP sign-in fails with "No account is associated with this number". There was no way to give such a customer a login except a seed script run against the database. The product owner chose (2026-10-15): an agency-registered customer gets their login automatically on their first phone + OTP sign-in.

## Business rule

When `POST /auth/otp/verify` matches the code and no login exists for that phone number in that tenant, create one if the tenant has a customer with that phone number who:

- has no login yet, and
- is `onboarding`, `pending_approval` or `active` (onboarding customers need to sign in to finish KYC; `inactive`, `blocked` and `closed` customers get no new way in).

The login has role `customer`, the customer's branch, the phone number, no email and no password. It is linked to the customer (`customer.identity_user_id`) in the same transaction. Otherwise the response is unchanged (`InvalidCredentialsError`, same generic message). Drivers and staff are never created here. Self-registration of unknown numbers (`FR-CM-01`) stays out of scope.

## Design

- Domain: `Customer.can_get_app_login` holds the eligibility rule.
- Application: new port `CustomerLoginProvisioner` (`application/identity/ports.py`); `VerifyOtpUseCase` calls it only when the phone lookup finds no user, then continues with the existing active/tenant/license checks.
- Infrastructure: `SqlAlchemyCustomerLoginProvisioner` opens one session scoped to the resolved tenant (RLS), loads the customer through `SqlAlchemyCustomerRepository`, inserts the user through a new shared `insert_identity_user` (which also materialises the role's permissions, now reused by `SqlAlchemyStaffUserRepository.add`), links it and commits.
- API: `get_customer_login_provisioner` wires it into `routers/auth.py::otp_verify`. No request/response or OpenAPI change.
- No migration.

## Testing

- Unit: `can_get_app_login` for every status and for a customer who already has a login.
- Integration (real PostgreSQL + Redis): first sign-in creates and links a `customer` login with permissions; a second sign-in reuses it; inactive/blocked/closed customers get none; a customer of another tenant gets none.
