# STATUS — Phase 6: Authentication & Authorization

**Feature:** 06-authentication-authorization
**Plan:** [PLAN.md](./PLAN.md) · **Tasks:** [TASKS.md](./TASKS.md)

---

## Status

**COMPLETE — all 12 areas (A–L) verified.** Started and finished 2026-08-10, single continuous session, on explicit instruction, immediately after Phase 5 closed out.

## Progress

| Area | State |
|---|---|
| A — Backend: Identity domain layer | ✅ Verified |
| B — Backend: Identity application layer | ✅ Verified |
| C — Backend: Persistence | ✅ Verified |
| D — Backend: Identity infrastructure adapters | ✅ Verified |
| E — Backend: API layer | ✅ Verified |
| F — Backend: Security & RBAC tests | ✅ Verified |
| G — Frontend: Data-access additions | ✅ Verified |
| H — Frontend: Shell-bypass routing restructure | ✅ Verified |
| I — Frontend: Login feature library | ✅ Verified |
| J — Mobile: `auth`/`api_client` packages | ✅ Verified |
| K — Mobile: wiring into both apps + CI | ✅ Verified |
| L — Cross-cutting: OpenAPI regen, ADRs, docs | ✅ Verified (this document) |

## What Was Built

### Backend (Areas A–F)

A complete, hand-built Identity module: JWT (RS256, `pyjwt[crypto]`) access tokens with refresh-token rotation and reuse detection, Argon2id password hashing, OTP login for Customer/Driver, RBAC (claims-based `scope` JWT claim for fast checks, live DB re-query for four high-sensitivity actions), and password reset — all under strict per-tenant RLS.

**The core architectural problem** — looking up a user by email/phone before any tenant context exists, under `FORCE ROW LEVEL SECURITY` — is solved with narrowly-scoped `SECURITY DEFINER` PostgreSQL functions, `search_path`-pinned, with `EXECUTE` explicitly revoked from `PUBLIC` before being re-granted only to `lpg_app`/`lpg_app_uat` (PostgreSQL grants `EXECUTE` to `PUBLIC` by default on a new function — caught via `information_schema.role_routine_grants` before it became a real hole). Full reasoning: **ADR-035**.

**A critical, previously-latent FastAPI bug was found and fixed**, unrelated to auth specifically but caught only because this phase finally exercised the affected path end-to-end: `from __future__ import annotations` + `TYPE_CHECKING`-only imports inside `Annotated[X, Depends(...)]` silently breaks `typing.get_type_hints()` for the whole function, making FastAPI treat every dependency as a required query field (a 422 on every parameter, no error pointing at the real cause). Found via a genuine end-to-end HTTP smoke test (`test_auth_endpoints_smoke.py`), not a mocked one. Fixed in every affected router/dependency module, and proactively in `dependencies/unit_of_work.py` — an identical latent bug from Phase 2, never triggered before because no router had used it yet.

**259 backend tests passing** (up from 182 at Phase 2 close-out), `mypy --strict` clean (121 source files), `ruff` clean, `import-linter` 5/5 contracts kept.

### Frontend (Areas G–I)

`AuthTokenStore` (in-memory signal, never `localStorage`), `authInterceptor` (bearer attach + one silent refresh-and-retry on 401), `authGuard`/`permissionGuard`, and `AuthService` — all in `libs/shared/data-access`. The app shell was restructured (ADR-036) so `/login` renders without the sidebar/top-bar chrome: `app.html` is now a bare `<router-outlet />`, `ShellLayout` hosts what it used to, and `/login` is declared as a sibling route ahead of `ShellLayout`'s own catch-all child — Angular's router tries top-level routes in declaration order, so this ordering matters, not just the nesting.

`libs/auth/feature-login` is the codebase's first `type:feature`-tagged library and first real Reactive Forms usage: `LoginPage`, `ForgotPasswordPage` (no-enumeration success state), `ResetPasswordPage`.

**A pre-existing Jest/ESM gap was found and fixed while adding the new lib**: PrimeNG's `ButtonDirective` pulls in `@primeui/license-manager` → `@noble/ed25519`, an ESM-only `.js` package Jest's default `transformIgnorePatterns` doesn't transform. The fix already existed in `shared-ui`/`dashboard`'s own `jest.config.cts` (from when `shared-ui` first hit this in an earlier phase) — the new lib's config just needed the same pattern copied in, not a novel fix.

Full frontend gate — lint/test/build across all 7 projects, `prettier --check`, token-generation `--check` — all pass. Verified end-to-end in a real browser: navigating to `/` with no session redirects to `/login?redirectTo=%2F`; form validation renders correctly; `/login/forgot-password` navigates and renders.

### Mobile (Areas J–K)

Two new packages: `api_client` (hand-written `dio` wrapper, ADR-037 — deferring spec-generation for ~8 endpoints, with an explicit revisit trigger) and `auth` (`TokenStorage`/`SecureTokenStorage`, `AuthRepository`/`ApiAuthRepository`, `AuthController` bridging session state to `go_router`'s `refreshListenable` via `ChangeNotifier`). Both apps get an OTP sign-in screen and `redirect:`-based route guards.

**A real Dio-specific behavior had to be designed around**: `dio.fetch()` on retry re-runs the *entire* interceptor chain (unlike the Dashboard's RxJS interceptor, which continues only the remaining chain) — `refreshAccessToken`'s implementation must persist the new token to the same store `getAccessToken` reads from before returning it, or the retry silently reattaches the stale token. Caught by a test that initially failed with the stale token still attached; documented inline in `ApiClient.onError` and exercised directly in `api_client_test.dart`.

**44 mobile tests passing** across all 7 packages/apps (was 18 at Phase 5 close-out) — `api_client` 9, `auth` 15, `driver_app` 3, `customer_app` 3, `core` 3, `design_system` 4, `local_storage` 7. `dart format --set-exit-if-changed`/`flutter analyze`/`flutter test` all clean, run per-package matching `.github/workflows/mobile-ci.yml`'s matrix exactly (Melos itself still doesn't recognize this workspace with the installed Melos 8.2.2, the same tooling-version mismatch Phase 5's STATUS.md already noted — not a blocker, CI doesn't use Melos either).

## Verification Summary

| Stack | Tests | Gate |
|---|---|---|
| Backend | 259 passing | `pytest`, `mypy --strict` (121 files), `ruff check`/`format --check`, `import-linter` (5/5) |
| Frontend | 56 passing across 7 projects (5+9+8+13+13+8) | `nx run-many -t lint test build --all`, `prettier --check`, token-gen `--check` |
| Mobile | 44 passing across 7 packages/apps | `dart format --set-exit-if-changed`, `flutter analyze`, `flutter test`, per `.github/workflows/mobile-ci.yml`'s matrix |

**359 tests passing overall** across all three stacks for this phase's verification pass.

## Commits

1. `feat(backend): implement Phase 6 identity, JWT auth, and RBAC` (`576fea6`) — Areas A–F.
2. `feat(frontend): wire JWT auth into the Dashboard shell and add login UI` (`f827d58`) — OpenAPI/client regen, Areas G–I.
3. `feat(mobile): add auth/api_client packages and wire OTP sign-in into both apps` (`04c96fb`) — Areas J–K.

## Still Open (not blockers)

- **WebSocket connection/subscription authorization** — Phase 3's `RealtimePublisher` was built without it, deliberately (needed real Authentication first). Now tracked as its own immediate fast-follow, not tied to a later numbered phase — see `docs/architecture/15-architecture-decision-records.md`'s Deferred Decisions table.
- **Staff/customer/driver user-management CRUD** — Phase 7 scope, per this phase's own `PLAN.md`.
- **Real OTP/email delivery** — logging-only dev adapters today; real providers are Phase 14 (Notifications).
- **Mobile OTP tenant resolution** — the "Tenant ID" text field on both apps' `LoginScreen` is an explicit placeholder; real client-bootstrapping (subdomain, build flavor, or a dedicated screen) is out of scope, per `RequestOtpUseCase`'s own docstring.
- **MFA, Entra ID SSO** — both explicitly deferred (schema seam only for SSO); see `PLAN.md`'s Scope Boundaries.
- **CI-runner confirmation carried over from Phase 5** — `mobile/packages/local_storage`'s SQLCipher build hook (ADR-034) was still only verified locally as of Phase 5 close-out; unaffected by this phase, tracked separately.

## Last Updated

2026-08-10 — phase complete, all 12 areas verified across all three stacks.
