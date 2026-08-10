# TASKS — Phase 7: Administration & Tenant/Master Data

**Feature:** 07-administration-tenant-master-data
**Plan:** [PLAN.md](./PLAN.md)

---

## Area A — Backend: `tenant.tenant` Reconciliation

- [x] A1. Migration `b1c4a9e7d2f3` — adds `status` (CHECK trial/active/suspended/closed, default trial), `subscription_plan`, `primary_contact_email`, `country` with server defaults.
- [x] A2. `Tenant` aggregate — `TenantStatusChanged` event, `activate()`/`suspend()`/`reactivate()`/`close()` lifecycle, `_transition_to()` helper.
- [x] A3. `TenantModel`/`SqlAlchemyTenantRepository` extended for the new columns.
- [x] A4. 15 unit tests (`tests/unit/test_domain_tenant.py`).

## Area B — Backend: Branch & Warehouse

- [x] B1. Migration `c3e8f1a5b6d7` — `tenant.branch`, `tenant.warehouse`, standard tenant-scoped RLS; adds the FK Phase 6 left dangling (`identity.identity_user.branch_id` → `tenant.branch.id`).
- [x] B2. `Branch`/`Warehouse` domain aggregates; `application/tenant/branch.py`/`warehouse.py` use cases; `BranchRepository`/`WarehouseRepository` protocols.
- [x] B3. `BranchModel`/`WarehouseModel` + `SqlAlchemyBranchRepository`/`SqlAlchemyWarehouseRepository` — **found and fixed** a `NotNullViolationError` from a missing ORM `server_default` mirror.
- [x] B4. Unit + integration tests (`test_domain_branch_warehouse.py`, `test_branch_warehouse_repositories.py`).

## Area C — Backend: Cylinder Type

- [x] C1. Migration `d4f9a2b8e1c6` — `tenant.cylinder_type` (name unique-per-tenant, weight_kg CHECK > 0, is_active).
- [x] C2. `CylinderType` domain aggregate + `application/tenant/cylinder_type.py` use cases.
- [x] C3. **Found and fixed**: `AuditRecorder._jsonable()` didn't handle `Decimal` (`weight_kg`) — added a `Decimal → str` branch.
- [x] C4. Unit + integration tests (`test_domain_cylinder_type.py`, `test_cylinder_type_repository.py`).

## Area D — Backend: Tenant Configuration

- [x] D1. Migration `e5a1c7d3f9b2` — `tenant.tenant_configuration`, historized (unique on tenant_id+config_key+effective_from).
- [x] D2. `TenantConfiguration` aggregate, `RECOGNIZED_CONFIG_KEYS`, `TenantConfigurationResolver` domain service.
- [x] D3. `application/tenant/tenant_configuration.py` use cases.
- [x] D4. Unit + integration tests — **found and fixed** a test-authoring bug (reused `UnitOfWork` across two commands; `commit()` is idempotent-after-first-call).

## Area E — Backend: Price List

- [x] E1. Migration `f6b2d8e4a0c7` — `tenant.price_list`, `UNIQUE NULLS NOT DISTINCT` (PostgreSQL 15+) on the full dimension tuple.
- [x] E2. `PriceListEntry` aggregate, `CUSTOMER_TYPES`, `EffectivePriceResolver` domain service.
- [x] E3. `application/tenant/price_list.py` use cases.
- [x] E4. Unit + integration tests (`test_domain_price_list.py`, `test_price_list_repository.py`).

## Area F — Backend: Feature Flags (Full System)

- [x] F1. Migration `a7c3e9f5b1d8` — new `platform` schema (no RLS), `platform.feature_flag`; `tenant.feature_flag_override` (standard RLS).
- [x] F2. `FeatureFlag`/`FeatureFlagOverride` domain classes, `_rollout_bucket()` (SHA256-based consistent hashing), `FeatureFlagService.is_enabled()` (schedule → override → default → rollout).
- [x] F3. `application/platform/` ports + use cases.
- [x] F4. `FeatureFlagModel` (new `infrastructure/persistence/models/platform.py`), `FeatureFlagOverrideModel` (appended to `tenant.py`); `SqlAlchemyFeatureFlagRepository` (new `repositories/platform.py`), `SqlAlchemyFeatureFlagOverrideRepository` (appended to `repositories/tenant.py`).
- [x] F5. 19 unit tests including a deterministic rollout-boundary test (`test_domain_feature_flag.py`); integration tests (`test_feature_flag_repositories.py`).

## Area G — Backend: Staff User Management

- [x] G1. `IdentityUser.change_role()` — validates against the 8 confirmed role codes, records `IdentityUserRoleChanged`.
- [x] G2. `StaffUserRepository` protocol (`application/identity/ports.py`); `InviteStaffUserUseCase`/`DeactivateStaffUserUseCase`/`ReassignRoleUseCase`/`ListStaffUsersUseCase` (new `application/identity/staff_user.py`).
- [x] G3. `SqlAlchemyStaffUserRepository` (plain RLS-scoped, post-authentication — distinct from the `SECURITY DEFINER`-based `SqlAlchemyIdentityUserRepository` used for pre-auth login/OTP/refresh) — **found and fixed** a `save()` bug silently dropping `password_hash`/`failed_login_count`/`locked_until`.
- [x] G4. `IdentityUserModel` — **found and fixed** the same ORM `server_default` gap as Area B.
- [x] G5. Unit tests (`TestChangeRole` in `test_domain_identity_user.py`); 5 integration tests (`test_staff_user_repository.py`).

## Area H — Backend: Audit Log Read API

- [x] H1. `application/audit/` — `AuditLogRepository` port, `ListAuditLogUseCase`.
- [x] H2. `SqlAlchemyAuditLogRepository` (new `infrastructure/persistence/repositories/audit.py`) — cursor-based keyset pagination on `(performed_at, id)`, `_encode_cursor`/`_decode_cursor`.
- [x] H3. 5 integration tests (`test_audit_log_repository.py`).

## Area I — Backend: API Layer

- [x] I1. Migration `b8d4e0a6c2f9` — 4 new permission codes, additive `INSERT...SELECT` joined on role.code.
- [x] I2. `api/v1/dependencies/admin.py` — ~10 dependency-wiring functions.
- [x] I3. `api/v1/schemas/admin.py` — ~30+ Pydantic models.
- [x] I4. `api/v1/routers/admin.py` — 26 endpoints under `/admin`, mounted in `api/app.py`.
- [x] I5. `pyproject.toml` — 5 new `ignore_imports` entries for the "SQLAlchemy stays inside infrastructure" import-linter contract.

## Area J — Backend: Tests

- [x] J1. 7 RBAC tests (`test_admin_rbac.py`) — claims-based allow/deny per endpoint, plus a live-check test for `feature_flags:manage_platform`.
- [x] J2. 3 endpoint smoke tests (`test_admin_endpoints_smoke.py`).

## Area K — Backend: Full Validation Gate

- [x] K1. `pytest` — 369 tests passing (up from 259 at Phase 6 close-out).
- [x] K2. `mypy --strict`, `ruff check`/`format --check`, `import-linter` (5/5 contracts) — all clean.

## Area L — Frontend: Data-Access Additions

- [x] L1. OpenAPI spec regenerated (`scripts/export_openapi.py`) → `npm run generate:api-client`.
- [x] L2. 9 new services in `libs/shared/data-access/src/lib/` (`admin-tenant`, `admin-branch`, `admin-warehouse`, `admin-cylinder-type`, `admin-tenant-configuration`, `admin-price-list`, `admin-feature-flag`, `admin-staff-user`, `admin-audit-log`) — all follow `AuthService`'s existing pattern; barrel `index.ts` updated.

## Area M — Frontend: Admin Feature Libraries

- [x] M1. `libs/admin/feature-tenant-settings` — branches/warehouses/cylinder-types/tenant-configuration/price-list pages, 5 exported route arrays.
- [x] M2. `libs/admin/feature-users` — staff list, invite form, deactivate/reassign-role actions.
- [x] M3. `libs/admin/feature-audit-log` — filterable, cursor-paginated log viewer.
- [x] M4. `libs/admin/feature-flags` — platform flag management (`super_admin`) + tenant override toggles (`agency_admin`).
- [x] M5. `tsconfig.base.json` — 5 new path aliases (4 admin libs + `@lpg/shared/ui/app-shell`).
- [x] M6. `app.routes.ts` — 9 new lazy `loadChildren` routes under `/admin/*`, each `canActivate: [permissionGuard(...)]`; `ShellLayout` gains an "Administration" nav group.
- [x] M7. **Found and fixed** a critical bundle-budget failure (main.js 645KB → 1.38MB, over the 1MB hard error threshold): `ShellLayout` importing from `@lpg/shared/ui`'s barrel transitively pulled `ag-grid-community` into the eager bundle. Fixed via a new secondary Nx entry point `libs/shared/ui/src/app-shell.ts`.
- [x] M8. **Found and fixed** (during manual browser verification, after N's gate had already passed): all 8 `<lpg-data-grid>` usages rendered at 0px height — no ancestor gave the grid an explicit `block-size`. Fixed by wrapping each in a `.admin-page__grid { block-size: 400px; }` container, matching the component's own Storybook story.

## Area N — Frontend: Full Validation Gate

- [x] N1. `nx run-many -t lint test build --all` — 56 tests passing across 6 tested projects, all lint/build clean.
- [x] N2. `prettier --check`, design-token generation `--check`.
- [x] N3. Manual smoke in a real browser: login as seeded `demo-admin@example.com` (`agency_admin`), Administration nav renders all 8 items, Branch create round-trip verified at the API level (`POST` 201 → `GET` returns the new row) and now visibly renders in the grid (post-M8 fix), Audit Log page shows the resulting audit row.
- [x] N4. **Found and fixed** (pre-existing, not Phase-7-specific) a double `/api/v1` URL prefix bug in `environment.ts`/`environment.prod.ts`, only surfaced by this phase's first real manual login test against a live backend.

## Area O — Documentation Close-Out

- [x] O1. `docs/data/01-domain-model.md` §4.1 corrected — aggregate-root divergence documented (Branch/Warehouse/TenantConfiguration/CylinderType/PriceListEntry as independent roots, not Tenant-nested entities); `FeatureFlag`/`FeatureFlagOverride` added (§4.12–4.13); aggregate catalog (§3) and domain services table (§5) extended.
- [x] O2. `docs/data/03-database-schema.md` — added `tenant.price_list`, new `platform` schema section (`platform.feature_flag`), `tenant.feature_flag_override`; documented the previously-undocumented `tenant.tenant.slug` column and the `identity_user.branch_id` FK now being real.
- [x] O3. This directory (`PLAN.md`/`TASKS.md`/`STATUS.md`).
- [x] O4. `planning/current_phase.md` and `knowledge/12-current-status.md` updated.
