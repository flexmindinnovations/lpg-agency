# STATUS — Phase 7: Administration & Tenant/Master Data

**Feature:** 07-administration-tenant-master-data
**Plan:** [PLAN.md](./PLAN.md) · **Tasks:** [TASKS.md](./TASKS.md)

---

## Status

**COMPLETE — all 15 areas (A–O) verified.** Started and finished 2026-08-10, single continuous session, on explicit instruction, immediately after Phase 6 closed out. Not yet committed to git — all changes are staged in the working tree, pending explicit user confirmation to commit.

## Progress

| Area | State |
|---|---|
| A — Backend: `tenant.tenant` reconciliation | ✅ Verified |
| B — Backend: Branch & Warehouse | ✅ Verified |
| C — Backend: Cylinder Type | ✅ Verified |
| D — Backend: Tenant Configuration | ✅ Verified |
| E — Backend: Price List | ✅ Verified |
| F — Backend: Feature flags (full system) | ✅ Verified |
| G — Backend: Staff user management | ✅ Verified |
| H — Backend: Audit log read API | ✅ Verified |
| I — Backend: API layer | ✅ Verified |
| J — Backend: Tests | ✅ Verified |
| K — Backend: Full validation gate | ✅ Verified |
| L — Frontend: Data-access additions | ✅ Verified |
| M — Frontend: Admin feature libraries | ✅ Verified |
| N — Frontend: Full validation gate | ✅ Verified |
| O — Documentation close-out | ✅ Verified (this document) |

## What Was Built

### Backend (Areas A–K)

Nine new Alembic migrations spanning three bounded contexts: `tenant.tenant` reconciliation (status/subscription_plan/primary_contact_email/country + a `trial → active → suspended/closed` lifecycle), `tenant.branch`/`tenant.warehouse`/`tenant.cylinder_type` (standard tenant-scoped RLS master data), `tenant.tenant_configuration`/`tenant.price_list` (append-only/historized, each resolved by its own point-in-time domain service — `TenantConfigurationResolver`/`EffectivePriceResolver`), and a new `platform` schema for `platform.feature_flag` (no RLS, the same non-RLS-reference-data precedent `identity.role`/`identity.permission` set in Phase 6) paired with tenant-scoped `tenant.feature_flag_override`.

**Feature flags were built as the full system the user explicitly chose** over a simpler per-tenant boolean table: `FeatureFlagService.is_enabled(flag_key, tenant_id)` resolves schedule (not-yet-started/already-ended → false) → tenant override (short-circuits) → platform default → rollout percentage (consistent SHA256-based hash of tenant_id mod 100), unit-tested against all four branches including a deterministic rollout-boundary case.

**Staff user management extends the existing Identity bounded context** (per the user's explicit choice), not a new indirection layer: `IdentityUser.change_role()`, and four new use cases (`InviteStaffUserUseCase` reuses Phase 6's password-reset-token mechanism as the "set your initial password" flow — no new invite-token concept — `DeactivateStaffUserUseCase`, `ReassignRoleUseCase`, `ListStaffUsersUseCase`). A new `SqlAlchemyStaffUserRepository` (plain RLS-scoped, post-authentication) sits deliberately apart from Phase 6's `SECURITY DEFINER`-based `SqlAlchemyIdentityUserRepository` (pre-authentication) — the two are never interchangeable despite both wrapping `IdentityUser`.

**A new 26-endpoint `admin.py` router** under `/admin`, gated by 4 new additive permission codes (`users:manage`, `feature_flags:manage_tenant`, `feature_flags:manage_platform` — live-checked, `super_admin`-only — `audit:read`), reusing Phase 6's `tenant:configure` for the master-data CRUD.

**369 backend tests passing** (up from 259 at Phase 6 close-out), `mypy --strict` clean, `ruff` clean, `import-linter` 5/5 contracts kept.

### Frontend (Areas L–N)

9 new data-access services in `libs/shared/data-access`, following `AuthService`'s established pattern (no new `libs/admin/data-access` — Nx's `type:data-access → type:util`-only boundary rule blocked a new data-access lib from importing the generated OpenAPI client, so the new services live alongside `AuthService` instead). 4 new `type:feature`-tagged Nx libraries under `libs/admin/` (the second-ever use of that pattern after `libs/auth/feature-login`), with 8 page components wired into 9 new lazy `/admin/*` routes, each behind `permissionGuard` — the guard's first real consumer since Phase 6 built it.

**56 tests passing** across the 6 tested frontend projects (unchanged from Phase 6 — the new admin libs have no dedicated component-level tests; coverage for the new routes comes from the existing shell/route-structure tests).

## Bugs Found and Fixed

Seven genuine, previously-latent bugs — full detail in `PLAN.md`'s dedicated section:

1. ORM `server_default` gaps (5 models) causing `NotNullViolationError` on first plain-insert.
2. `Decimal` not JSON-serializable in `AuditRecorder._jsonable()`.
3. A test-authoring UnitOfWork-reuse mistake (`commit()` idempotent-after-first-call).
4. `SqlAlchemyStaffUserRepository.save()` silently dropping password/lockout fields.
5. Frontend eager-bundle AG Grid leak (main.js 645KB → 1.38MB, over budget) — fixed via a secondary Nx entry point.
6. A pre-existing double `/api/v1` URL prefix bug, only surfaced by this phase's first real manual browser login.
7. AG Grid rendering at 0px height across all 8 new admin pages — found during manual verification (the component's own Storybook story already documented the exact pitfall), fixed by wrapping every grid usage in an explicitly-heighted container.

## Verification Summary

| Stack | Tests | Gate |
|---|---|---|
| Backend | 369 passing | `pytest`, `mypy --strict`, `ruff check`/`format --check`, `import-linter` (5/5) |
| Frontend | 56 passing across 6 tested projects | `nx run-many -t lint test build --all`, `prettier --check`, token-gen `--check` |

**Manual browser verification** (real local Docker Postgres/Redis backend, real Dashboard dev server): logged in as seeded `demo-admin@example.com` (`agency_admin`, tenant "Demo Agency"); confirmed all 8 Administration nav items render; created a Branch ("Nashik West" / "Maharashtra") — verified the full CRUD round-trip at the API level and, after the AG Grid height fix, confirmed the row renders visibly in the grid; confirmed the resulting audit-log row appears in the Audit Log page's grid.

## Still Open (not blockers)

- **WebSocket connection/subscription authorization** — unchanged from Phase 6, still its own fast-follow.
- **Mobile Administration UI** — explicitly out of scope; Administration is back-office/Dashboard-only.
- **Real invite-email delivery** — logging-only dev adapter today; real providers are Phase 14 (Notifications).
- **Tenant self-service signup/provisioning** — remains an elevated/seed operation, unchanged.
- **Dedicated component-level tests for the 8 new admin pages** — the frontend gate (lint/build/existing route tests) passed, but no new Jest specs were written for the individual page components themselves; worth a follow-up if these pages see heavy iteration.
- **Not yet committed** — all Phase 7 changes are in the working tree; awaiting explicit user go-ahead to commit per this session's standing git-safety practice.

## Last Updated

2026-08-10 — phase complete, all 15 areas verified across backend and frontend.
