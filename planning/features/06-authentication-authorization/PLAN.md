# PLAN — Phase 6: Authentication & Authorization

**Feature:** 06-authentication-authorization
**Started / finished:** 2026-08-10, single continuous session, on explicit instruction.

---

## Objective

Replace Phase 2's interim `HeaderTenantResolver` (never a security boundary, never wired to a reachable endpoint) with a real, hand-built Identity module: JWT (RS256) + Argon2id password auth, OTP login for Customer/Driver, RBAC (claims-based and live), and password reset — across all three stacks (backend, Dashboard, mobile).

## Why now

Three concrete things were already waiting specifically on real authentication existing:
- The `HeaderTenantResolver` itself (Phase 2's documented placeholder).
- DW-12 — making tenant-scoped sessions structurally mandatory, not just conventionally always-provided.
- Phase 3's excluded WebSocket subscription authorization (`RealtimePublisher` built without it) — split into its own immediate fast-follow rather than bundled into this phase (see Scope Boundaries).

Nothing past this point in the roadmap can be built against a trustworthy tenant/user context otherwise.

## Decisions resolved immediately ahead of this plan

- **D-38** (role-list ambiguity): confirmed **8 roles** — "Warehouse Staff" is Warehouse Manager renamed, not a second tier.
- **WebSocket authentication**: split out of this pass into an immediate fast-follow — it needs a from-scratch `ConnectionManager` + Redis fan-out that has never existed in this codebase, and nothing in this plan's frontend/mobile work depends on it.

## Scope Boundaries (decided, not re-litigated during implementation)

- No staff/customer/driver "user management" CRUD — Roadmap Phase 7 owns that. Verification accounts come from a dev/CI-only seed script.
- MFA out of scope (SRS recommends it for Super Admin only; deferred).
- Entra ID SSO: schema seam only (`identity_user.sso_subject`/`sso_provider`, nullable), no working OAuth flow.
- Password/reset-token delivery: logging-only dev adapters (`EmailSender`, `OtpDeliveryPort`); real providers are Phase 14 (Notifications) scope.
- Password policy: NIST 800-63B-style defaults (length-focused, min 12 chars, no forced composition; lockout after 5 consecutive failures), configurable via `Settings`.
- JWT: `pyjwt[crypto]`, RS256. Password hashing: `argon2-cffi` (Argon2id).
- Flutter `api_client`: hand-written thin `dio` wrapper for this phase's ~8 auth endpoints, not spec-generated (ADR-037, explicit revisit trigger).

Full rationale for every decision above: **ADR-035** (JWT/Argon2/RS256 + `SECURITY DEFINER` tenant resolution), **ADR-036** (shell-bypass routing), **ADR-037** (hand-written Flutter `api_client`).

## Implementation Areas

| Area | Scope |
|---|---|
| A | Backend: Identity domain layer (`IdentityUser`, `RefreshToken`, `PasswordResetToken` aggregates/entities) |
| B | Backend: Identity application layer (ports, use cases, `PermissionChecker`) |
| C | Backend: Persistence — migrations, models, repositories, `SECURITY DEFINER` functions |
| D | Backend: Infrastructure adapters (password hasher, token hasher, JWT signer, OTP service, `JwtTenantResolver`) |
| E | Backend: API layer — dependencies, `auth` router (8 endpoints), schemas |
| F | Backend: Security & RBAC tests |
| G | Frontend: Data-access additions (token store, interceptor, guards, `AuthService`) |
| H | Frontend: Shell-bypass routing restructure (`ShellLayout`, ADR-036) |
| I | Frontend: Login feature library (`libs/auth/feature-login`) |
| J | Mobile: `auth` and `api_client` packages |
| K | Mobile: wiring into both apps + CI |
| L | Cross-cutting: OpenAPI regen, ADRs, documentation close-out |

Full task-by-task breakdown: [TASKS.md](./TASKS.md). Outcome and verification numbers: [STATUS.md](./STATUS.md).

## Build & Verification Order

1. Backend A → B → C → D (domain → application ports → migrations/models/repos → infra adapters) — nothing externally observable yet, `mypy --strict`/`ruff`/`lint-imports` after each.
2. Backend E — routers/dependencies/`AppState` wiring, the `HeaderTenantResolver` → `JwtTenantResolver` rebind. Re-run `tests/tenant_isolation/` immediately after.
3. Backend F, written alongside D/E — the RBAC suite is what proves Area C's seeded permission matrix is correct.
4. Full backend gate: `pytest`, `mypy --strict`, `ruff check`, `ruff format --check`, `lint-imports`.
5. L's OpenAPI regen — `scripts/export_openapi.py`, then `npm run generate:api-client`.
6. Frontend G → H → I — data-access first (compiles standalone), then the shell restructure (verified the existing home route still worked before adding `/login`), then the login feature lib.
7. Full frontend gate: `nx run-many -t lint test build --all`, `prettier --check`, token-generation `--check`.
8. Mobile J → K — `api_client` first (nothing depends on it yet), then `auth` (depends on `api_client`), then wire both apps.
9. Full mobile gate per package/app, matching `.github/workflows/mobile-ci.yml`'s matrix exactly.
10. Manual smoke: dashboard dev server, verified `/` → `authGuard` redirect → `/login` → form validation → `/login/forgot-password` navigation, in a real browser.
11. Documentation pass (this directory + ADR-035/036/037 + `planning/current_phase.md`/`knowledge/12-current-status.md`).

## Explicitly Not Done (deferred, not oversight)

- WebSocket connection/subscription authorization — immediate fast-follow, tracked in `docs/architecture/15-architecture-decision-records.md`'s Deferred Decisions table.
- Staff/customer/driver user-management CRUD — Phase 7.
- MFA, Entra ID SSO — see Scope Boundaries above.
- Real OTP/email delivery providers — Phase 14 (Notifications).
- OTP login UI on the Dashboard — staff sign in with a password only; OTP is the mobile Customer/Driver path.
- Client-side tenant bootstrapping (subdomain/build-flavor resolution) for the mobile OTP screens — a plain "Tenant ID" text field is the explicit placeholder; `RequestOtpUseCase`'s own docstring defers real tenant resolution past this phase.
