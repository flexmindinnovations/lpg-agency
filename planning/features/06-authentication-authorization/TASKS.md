# TASKS — Phase 6: Authentication & Authorization

**Feature:** 06-authentication-authorization
**Plan:** [PLAN.md](./PLAN.md)

---

## Area A — Backend: Identity Domain Layer

- [x] A1. `IdentityUser` aggregate — `tenant_id`/`branch_id` (nullable), `email`/`phone_number`/`password_hash` (nullable), `role`, `is_active`, `failed_login_count`, `locked_until`; `record_successful_login()`/`record_failed_login()`/`activate()`/`deactivate()`/`change_password_hash()`/`is_locked()`.
- [x] A2. `RefreshToken` entity — `rotate()` (raises on already-rotated/revoked), `revoke()`, `is_usable()`/`is_expired()`.
- [x] A3. `PasswordResetToken` entity — `mark_used()`, `is_usable()`.
- [x] A4. Domain events: `IdentityUserLoggedIn`, `IdentityUserLoginFailed`, `IdentityUserLocked`.
- [x] A5. 17 unit tests (`tests/unit/test_domain_identity_user.py`).

## Area B — Backend: Identity Application Layer

- [x] B1. Ports (`application/identity/ports.py`) — `PasswordHasher`, `TokenHasher`, `JwtSigner`, `OtpStore`, `OtpDeliveryPort`, `EmailSender`, `AuthenticatedPrincipal`, repositories.
- [x] B2. `LoginUseCase`, `VerifyOtpUseCase`/`RequestOtpUseCase`, `RefreshTokenUseCase`, `LogoutUseCase`, `RequestPasswordResetUseCase`/`ConfirmPasswordResetUseCase`.
- [x] B3. `PermissionChecker` — claims-based `has_permission()` + live `has_permission_live()` for the four high-sensitivity actions.
- [x] B4. New `ApplicationError` subclasses for the 7 reserved error codes (`INVALID_CREDENTIALS`, `ACCOUNT_LOCKED`, `REFRESH_TOKEN_INVALID`, `RESET_TOKEN_EXPIRED`, `OTP_MISMATCH`, `OTP_EXPIRED`, `WEAK_PASSWORD`).
- [x] B5. Documented divergence: no `UnitOfWork` in Identity use cases (see ADR-035, PLAN.md).

## Area C — Backend: Persistence

- [x] C1. Migration `fa52b77ec442` — `identity` schema, RBAC reference data (8 roles, permissions, role-permission matrix), `identity.identity_user`, `identity.user_role`, plus `SECURITY DEFINER` functions with `EXECUTE` revoked from `PUBLIC` and re-granted narrowly.
- [x] C2. Migration `10a62de534be` — `identity.refresh_token`, `identity.password_reset_token`, same `SECURITY DEFINER`/grant pattern.
- [x] C3. ORM models (`infrastructure/persistence/models/identity.py`) and repositories (`infrastructure/persistence/repositories/identity.py`), each SECURITY-DEFINER-backed.
- [x] C4. Verified PostgreSQL composite-function-returns-one-row-not-zero behavior directly (`docker exec psql`) before relying on it in repository code.
- [x] C5. 14 integration tests (`tests/integration/test_identity_repositories.py`); applied to `lpg_dev`/`lpg_test`/`lpg_uat` locally.

## Area D — Backend: Identity Infrastructure Adapters

- [x] D1. `Argon2PasswordHasher`, `Sha256TokenHasher`, `PyJwtSigner` (RS256).
- [x] D2. `OtpService` (Redis-backed) + logging-only `OtpDelivery`/`EmailSender` dev adapters.
- [x] D3. `JwtTenantResolver` — replaces `HeaderTenantResolver`, same `TenantResolver` protocol.
- [x] D4. `Settings` additions: JWT keys (ephemeral-generated only when `environment == "local"`), Argon2 cost params, lockout threshold/duration, OTP TTL, reset-token TTL, refresh-token TTL.

## Area E — Backend: API Layer

- [x] E1. `api/v1/dependencies/tenant.py` — one-line rebind to `JwtTenantResolver`.
- [x] E2. `api/v1/dependencies/identity.py` — `get_current_principal`, `require_permission`, `require_live_permission`.
- [x] E3. `api/v1/routers/auth.py` — 8 endpoints (`login`, `otp/request`, `otp/verify`, `refresh`, `logout`, `password/forgot`, `password/reset`, `me`).
- [x] E4. `api/v1/schemas/identity.py` — request/response models, `min_length=12` password validator.
- [x] E5. `AppState` gains `jwt_signer`/`password_hasher`; `create_app()` mounts `auth.router`.
- [x] E6. **Critical bug found and fixed**: `TYPE_CHECKING` + `from __future__ import annotations` silently breaking FastAPI `Depends()` resolution for entire router functions — fixed in every affected file, plus proactively in `dependencies/unit_of_work.py` (identical latent Phase 2 bug, never triggered). Full write-up: ADR-035.
- [x] E7. Genuine end-to-end HTTP smoke test (`tests/integration/test_auth_endpoints_smoke.py`) — the test that caught E6.

## Area F — Backend: Security & RBAC Tests

- [x] F1. Login lockout (enforced before password check runs; success resets the counter).
- [x] F2. Refresh-token-reuse triggers full session revocation, not just rejection of the one token.
- [x] F3. Live vs. claims-based permission check divergence (`PermissionChecker.has_permission` vs `has_permission_live`); `require_permission` dependency allow/deny.
- [x] F4. OTP request/verify/expiry/mismatch.
- [x] F5. Password reset request/confirm/expiry, and no-enumeration on request.
- [x] F6. Logout invalidates server-side (subsequent refresh with the same token fails); idempotent against an unknown token.
- [x] F7. 15 tests total in `tests/integration/test_auth_flows.py`, plus `test_jwt_signer.py`/`test_password_hasher.py`/`test_token_hasher.py`/`test_otp_service.py` unit tests.

## Area G — Frontend: Data-Access Additions

- [x] G1. `AuthTokenStore` — in-memory signal store, never `localStorage`.
- [x] G2. `authInterceptor` — bearer attach + one silent refresh-and-retry on 401, skipping the token-issuing endpoints themselves; `+ spec` (4 tests).
- [x] G3. `authGuard`, `permissionGuard`.
- [x] G4. `AuthService` — thin wrapper over the regenerated `AuthApi` functions; `restoreSession()` for page-reload session recovery via the refresh cookie.
- [x] G5. `app.config.ts` interceptor order updated: `[correlationIdInterceptor, authInterceptor, problemDetailsInterceptor]`.

## Area H — Frontend: Shell-Bypass Routing Restructure

- [x] H1. `app.html` → bare `<router-outlet />`; `ShellLayout` (`shell/shell-layout.ts`) hosts the shell chrome, `navGroups` moved from `app.ts`.
- [x] H2. `app.routes.ts` restructured — `/login` declared first (sibling, outside the guard), `ShellLayout` wraps existing routes as children behind `authGuard`.
- [x] H3. Shell-chrome tests moved to `shell/shell-layout.spec.ts`; `app.spec.ts` reduced to a smoke test + route-structure assertions.
- [x] H4. Verified the home route still renders correctly through `ShellLayout` before wiring `/login`.

## Area I — Frontend: Login Feature Library

- [x] I1. `libs/auth/feature-login` scaffolded (first `type:feature`-tagged lib).
- [x] I2. `LoginPage` — first Reactive Forms usage in this codebase, email/password validation, server error mapping (`INVALID_CREDENTIALS`/`ACCOUNT_LOCKED`).
- [x] I3. `ForgotPasswordPage` — no-enumeration success state regardless of whether the account exists.
- [x] I4. `ResetPasswordPage` — token from query param, password-match validator, `RESET_TOKEN_EXPIRED`/`WEAK_PASSWORD` handling.
- [x] I5. Fixed a pre-existing Jest/ESM gap (PrimeNG's `@noble/ed25519` via `primeng/button`'s license-manager) in the new lib's `jest.config.cts` `transformIgnorePatterns` — the fix already existed in `shared-ui`/`dashboard`'s configs, just not copied into this new lib initially.
- [x] I6. 13 component tests.

## Area J — Mobile: `auth` and `api_client` Packages

- [x] J1. `api_client` — `ApiClient` (Dio wrapper, bearer attach + refresh-and-retry interceptor), `AuthApi` (hand-written `/auth/*` methods returning `Result<T>`), `TokenPair`/`Principal` models, `mapDioError` (RFC 7807 → `Failure`).
- [x] J2. `auth` — `TokenStorage`/`SecureTokenStorage` (constructor-injectable-functions pattern, mirroring `DriftLocalDatabase`), `AuthRepository`/`ApiAuthRepository`, `AuthController` (bridges session state to `go_router`'s `refreshListenable` via `ChangeNotifier`).
- [x] J3. 24 tests (`api_client`: 9, `auth`: 15) — no mocking framework, fakes via constructor injection/`HttpClientAdapter`, matching `local_storage`'s established convention.

## Area K — Mobile: Wiring Into Both Apps + CI

- [x] K1. `auth_provider.dart` in both apps — `Provider<AuthController>` throwing `UnimplementedError` until overridden in `main()`, mirroring `local_database_provider.dart`.
- [x] K2. `main.dart` wires `TokenStorage` → `ApiClient` → `AuthApi` → `ApiAuthRepository` → `AuthController`, overriding the provider before `runApp()`.
- [x] K3. `router.dart` — `redirect:` + `refreshListenable: authController` in both apps, the go_router counterpart of `authGuard`.
- [x] K4. `LoginScreen` (OTP) in both apps — Tenant ID + phone request/verify flow.
- [x] K5. Existing `widget_test.dart` in both apps updated for the new build-time `authControllerProvider` dependency; added an unauthenticated-redirects-to-sign-in case.
- [x] K6. `.github/workflows/mobile-ci.yml` matrix gains `mobile/packages/api_client` and `mobile/packages/auth`.

## Area L — Cross-Cutting: OpenAPI Regen + ADRs + Docs

- [x] L1. `scripts/export_openapi.py` regenerated → `npm run generate:api-client` in `frontend/`.
- [x] L2. **ADR-035** — JWT/Argon2/RS256, `SECURITY DEFINER` tenant resolution.
- [x] L3. **ADR-036** — shell-bypass routing.
- [x] L4. **ADR-037** — hand-written Flutter `api_client`.
- [x] L5. `docs/data/17-api-security.md` §"Design Decisions" — JWT library confirmed (`pyjwt[crypto]`), Argon2id noted.
- [x] L6. This directory (`PLAN.md`/`TASKS.md`/`STATUS.md`).
- [x] L7. `planning/current_phase.md` and `knowledge/12-current-status.md` updated; DW-12 closed explicitly.
