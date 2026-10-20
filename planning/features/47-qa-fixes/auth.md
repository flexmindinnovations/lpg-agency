# QA fixes — identity, users, platform console, security, admin masters (auth)

Branch `qa-fix/auth`, based on `9cf5455`. Source: `/mnt/project-files/qa/qa-report-2026-10-20.md`.
Backend tests were run against a private DB, `lpg_test_auth` (cloned from `lpg_test_clean`), and Redis db 2.

## Findings → files → verification

| Finding | What changed | Main files | Verified by |
|---|---|---|---|
| DA-03 | Database errors are translated to friendly RFC 7807 problems by SQLSTATE: 23505 → 409, 23503 → 409, 23514/23502/22xxx → 422, 40001/40P01 → 409. SQL text is never sent. The UoW dependency no longer wraps errors as `HTTPException(500, str(e))`. | `infrastructure/persistence/errors.py`, `api/middleware/problem_details.py`, `api/app.py`, `api/v1/dependencies/unit_of_work.py` | `tests/unit/test_database_error_translation.py` |
| DA-01 | Self-deactivation and deactivating the last active agency admin are refused (409). New `PATCH /admin/users/{id}/reactivate`. Users page confirms before deactivating, offers Reactivate, has no action on your own row, and shows role/status chips and readable roles. | `application/identity/staff_user.py`, `routers/admin.py`, `libs/admin/feature-users/.../staff-users-page.ts`, `libs/shared/util/.../role-labels.ts` | `test_staff_user_repository.py`, `test_admin_endpoints_smoke.py::TestQaFixesThroughTheRealStack`, `staff-users-page.spec.ts` |
| DA-24 | Deactivate, reactivate, role change, permission change and password change write audit rows (with before/after) through the new `AuditTrail` port. | `application/audit/ports.py`, `infrastructure/persistence/audit_trail.py`, `dependencies/admin.py` | Same integration tests (audit-log assertions) |
| DA-05 | Migration `c48cbf996d8c` removes `inventory:load`, `customers:read`, `drivers:read` and `vehicles:read` from the driver role and from existing driver users. `GET /drivers/me` no longer needs `drivers:read`. | `alembic/versions/c48cbf996d8c_least_privilege_driver_permissions.py`, `routers/delivery.py` | `test_driver_least_privilege.py` |
| DA-08 | Emails link to `{dashboard_url}/set-password?token=` (invites, new agency) and `/reset-password?token=`. New top-level dashboard routes load the password page directly, so the token is kept; the set-up wording differs. New setting `LPG_DASHBOARD_URL`. | `password_reset.py`, `staff_user.py`, `config/settings.py`, `apps/dashboard/src/app/app.routes.ts`, `reset-password-page.ts` | `test_admin_endpoints_smoke.py::...test_an_invited_user_sets_a_password_from_the_link_and_signs_in` (invite → set password → login → token cannot be reused), `reset-password-page.spec.ts` |
| DA-09 | New `POST /platform/license/{tenant_id}/key` issues a new key for a pending licence. The licence drawer can activate with a pasted key or generate a new key. Closing the shown-once key dialog without activating, and revoking, both ask first. | `domain/license`, `application/license/issue_license.py`, `routers/platform.py`, `license-issuance-page.ts` | `test_license_key_replacement_and_tenant_sync.py`, `license-issuance-page.spec.ts` |
| DA-28 | Activating a licence, or changing the plan of an active licence, sets tenant status (trial → active) and plan to match the licence. Data migration `21a625272f0b` re-syncs existing tenants. Issue Licence lists only agencies with no licence. | `domain/tenant/tenant.py` (`apply_license`), `activate_license.py`, `alembic/versions/21a625272f0b_...py`, `license-issuance-page.ts` | Same tests, plus `test_domain_tenant.py` / `test_domain_license.py` |
| DA-19 | API: branch names are trimmed; blank (422), over 200 characters (422) and case-insensitive duplicates, inactive included (409), are refused. UI: Warehouses and Pricing branch pickers offer only active, named branches. Branch and godown names refuse whitespace. Deactivating a branch, godown or cylinder type asks first. | `domain/tenant/branch.py`, `application/tenant/branch.py`, `schemas/admin.py`, `libs/admin/feature-tenant-settings/*`, `libs/shared/util/.../form-validators.ts` | `test_branch_use_cases.py`, real-stack smoke, `branches-page.spec.ts`, `form-validators.spec.ts` |
| DA-26 / DO-29 / DO-30 | Tenant users land on Home after sign-in, not the AI Assistant. `authGuard` passes `returnUrl`, and the login page follows it only for a safe internal path that suits the session type. The sign-in form has no 12-character rule. The AI-off message no longer shows the internal key name. | `login-page.ts`, `auth.guard.ts`, `feature-ai-assistant.ts` | `login-page.spec.ts` (including the open-redirect cases), `auth.guard.spec.ts` |
| DO-31 | `permissionGuard` sends a denied tenant user to a new `/no-access` page; a platform session goes to `/platform`. Dispatch loads `/scales` only with `weighment:record`. Order detail loads active trips only with `routes:read`. | `permission.guard.ts`, `not-found.ts`, `app.routes.ts`, `feature-dispatch.ts`, `order-detail.ts` | `permission.guard.spec.ts`, `app.spec.ts` |
| DA-30 | `GET`/`PATCH /auth/me/profile` (display name, contact phone) and `POST /auth/me/password` (current password required; audited; rate limited). Migration `a9d2197ebb9b` adds `identity_user.display_name` and `contact_phone`. My Profile edits these, changes the password and shows the role in words. | `application/identity/my_profile.py`, `routers/auth.py`, `profile.ts`, `my-profile.service.ts` | `test_my_profile.py`, real-stack smoke, `profile.spec.ts` |
| DA-32 | `GET /admin/setup-progress` (needs `tenant:configure`) reports these steps: branch, warehouse, cylinder types, prices, GST, staff, drivers, vehicles. Home shows a checklist with links, and only for that permission. | `application/tenant/setup_progress.py`, `home/setup-checklist/setup-checklist.ts` | Real-stack smoke, `setup-checklist.spec.ts` |
| CA-03 | 429 responses have a friendly message, a `Retry-After` header and `retry_after_seconds`. OTP request limits are 30/hour per IP and 5/hour per phone number. | `limiter.py`, `problem_details.py`, `dependencies/identity.py` | `test_rate_limit_message.py` |
| CA-02 | **Not done here: handled by the +91 thread.** My phone-normalisation changes were reverted. The per-phone limit key uses the last 10 digits only and does not normalise. | — | — |
| SU-01/02/03 | Removed the stale `backend/scripts/seed_roles.py`. The demo seed adds an active Premium licence and syncs the tenant. `frontend/scripts/ensure-prime-license.mjs` (postinstall plus an nx target) creates the git-ignored PrimeNG licence file. `frontend/.npmrc` sets `legacy-peer-deps`. `CONTRIBUTING.md` documents these. | `backend/scripts/seed_demo_data.py`, `frontend/scripts/*`, `frontend/project.json`, `CONTRIBUTING.md` | Ran the seed on a fresh DB; ran the dashboard build |

## Migrations (all mine chain from `c8d4e2f6a1b3`)

`c8d4e2f6a1b3` → `c48cbf996d8c` (driver least privilege) → `21a625272f0b` (tenant ↔ licence sync, data only) → `a9d2197ebb9b` (profile columns).
All three have a downgrade.

## API changes (client regenerated in `450f67f`)

- New endpoints:
  - `PATCH /admin/users/{id}/reactivate`
  - `POST /platform/license/{tenant_id}/key`
  - `GET /admin/setup-progress`
  - `GET`/`PATCH /auth/me/profile`
  - `POST /auth/me/password`
- Changed responses:
  - `PrincipalResponse.display_name`
  - `StaffUserResponse.display_name` / `contact_phone`
  - `setup_path` is now `/set-password?token=…`
- Behaviour:
  - Database errors are now 409/422 problems.
  - Rate-limit 429 responses carry `Retry-After`.
  - Duplicate or blank branch names are 409/422.
  - Inviting with an unknown role is a 422.

## Test results

- **Backend:**
  - ruff, format, `mypy --strict` and import-linter (7 contracts) are all green.
  - `tests/unit` and the identity, licence and admin integration tests listed above pass on `lpg_test_auth`.
- **Frontend:**
  - Test and lint are green for: admin-feature-users, shared-util, shared-data-access, auth-feature-login, dashboard, admin-feature-license, admin-feature-tenant-settings, order-feature-orders, feature-dispatch, ai-feature-ai-assistant and platform-feature-agencies.
  - `nx build dashboard` succeeds, with an initial-bundle budget **warning**: 717 kB against a 700 kB budget. It is not an error, and I have not compared it with the base.

## Deferred

- **UX polish on the Employees, Settings and Platform Console › Agencies screens beyond the above.** I ran out of time. Users & Roles and Platform Console › Licenses did get the confirmation, readable-label and status-chip work.
- **The cylinder-units / inventory page still calls `/scales` for roles without `weighment:record` (DO-31).** The inventory thread is heavily rewriting `feature-inventory.ts`, so it should add the same guard used in `feature-dispatch.ts`.
- **The profile menu still derives a display name from the email.** It could use `PrincipalResponse.display_name` now that it exists.
- **Re-running the seed fails on `pk_route`.** This bug already exists on the base and was not touched here.

## Merge notes

1. Chain `c48cbf996d8c.down_revision` onto the merged alembic head. The other two migrations follow it.
2. After merging all threads, regenerate the API client (`uv run python scripts/export_openapi.py`, then `npm run generate:api-client`). My regenerated client already contains an unrelated `RouteStopResponse.order_number` from the base.
3. Expect small conflicts in:
   - `feature-dispatch.ts` and `order-detail.ts`: one guarded call each.
   - `home.ts`: one `<lpg-setup-checklist />` line plus an import.
   - `warehouses-page.ts`, `branches-page.ts`, `cylinder-types-page.ts` and `price-list-page.ts`: the UI thread also edits these.
   - `app.routes.ts`.
4. Production needs `LPG_DASHBOARD_URL` set to the public dashboard origin. Email links are absolute.
5. `lpg.api` import-linter ignores were added for `app -> persistence.errors` and `dependencies.admin -> persistence.audit_trail`.

## ADR draft (for the lead to file)

- **Identity changes are audited explicitly through an `AuditTrail` application port.** The identity repositories open their own sessions, so the generic SQLAlchemy audit hook does not see them. Use cases therefore record the action, entity, before/after and actor through `AuditTrail` (`SqlAlchemyAuditTrail`). Consequence: any new identity use case must call it.
- **The licence is the source of truth for tenant status and plan.** Activating a licence, or changing an active licence's plan, updates the tenant in the same unit of work: trial → active, `subscription_plan` = licence tier. A data migration aligns existing rows. Rejected alternative: deriving status at read time, which would mean a join on every tenant query.
- **Drivers get least privilege.** The driver role holds only what the driver app's own-delivery workflow needs. Self-service endpoints (`/drivers/me`) authorise by identity rather than by `*:read` list permissions. Future driver needs get narrow, self-scoped endpoints, not broad read grants.
- **Database errors never leave the API verbatim.** `DBAPIError` is translated by SQLSTATE into domain-neutral problem types at the API boundary, and unknown errors become a generic 500.
