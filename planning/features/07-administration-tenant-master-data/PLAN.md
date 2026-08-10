# PLAN — Phase 7: Administration & Tenant/Master Data

**Feature:** 07-administration-tenant-master-data
**Started / finished:** 2026-08-10, single continuous session, on explicit instruction, immediately after Phase 6 closed out.

---

## Objective

Give tenants master data to configure and a way to administer their own staff: branches, warehouses, cylinder types, tenant configuration (historized), pricing (historized), a full platform+tenant feature-flag system, staff user management, and a read path for the append-only audit log — across the backend and the Dashboard (no mobile work this phase).

## Why now

Phase 6 delivered real Authentication — every request now carries a verified `TenantContext`/`AuthenticatedPrincipal` — but there was still no master data for that tenant to configure. `tenant.tenant` was a three-column illustrative row from Phase 2, and nothing else in the `tenant` schema existed. Per `docs/implementation/roadmap.md`, Administration is Customer Management (Phase 8) and Inventory (Phase 9)'s hard prerequisite: branch, warehouse, and cylinder-type reference data are exactly what those modules will foreign-key against.

## Decisions resolved immediately ahead of this plan

Four design gaps had no prior specification anywhere in the docs, resolved with the user via `AskUserQuestion` ahead of this plan:
- **Feature flags** — chosen: a **full system** (platform-wide flags + tenant-level overrides + percentage rollout + scheduling), the larger, non-recommended option, over a simple per-tenant boolean table.
- **Pricing** — chosen: a **dedicated `price_list` table** (cylinder type x customer type x optional branch, historized), not a `tenant_configuration` jsonb blob.
- **User management ownership** — chosen: new use cases live in `application/identity/`, extending the existing `IdentityUser` aggregate/bounded context.
- **WebSocket connection/subscription authorization** — kept out of scope, tracked as its own separate fast-follow (unchanged from Phase 6's plan).

## Scope Boundaries

- **Backend + Dashboard only.** No mobile work — this is all back-office administration.
- **`identity.role`/`identity.permission`/`identity.role_permission` stay platform-managed, read-only.** "User management" means assigning one of the 8 existing roles to a staff account, never defining new roles/permissions.
- **`identity.user_role`** left exactly as-is — unused by the actual authorization path (which reads `identity_user.role` directly) since Phase 6; not a Phase 7 blocker.
- **No invite-email delivery** — staff invitation reuses the existing password-reset-token mechanism and the existing logging-only `EmailSender` dev adapter.
- **No tenant self-service signup/provisioning** — creating a new tenant remains an elevated/seed operation.
- **A documented divergence from `01-domain-model.md` §4.1**: Branch/Warehouse/TenantConfiguration were originally modeled as entities inside the `Tenant` aggregate. Implementation made each its own aggregate root instead — see `docs/data/01-domain-model.md` §4.1's Phase 7 implementation note for the full rationale. Corrected in place, same as D-38's residual note corrected `business/stakeholders.md` after Phase 6.

## New Permission Codes

Seeded via an additive migration (`b8d4e0a6c2f9`, existing rows never edited in place):

| Code | Meaning | Granted to |
|---|---|---|
| `users:manage` | Invite/deactivate/reassign-role for staff accounts | `agency_admin` |
| `feature_flags:manage_tenant` | Toggle tenant-level flag overrides | `agency_admin` |
| `feature_flags:manage_platform` | Create/edit platform-wide flags, rollout %, scheduling | `super_admin` only, **live-checked** |
| `audit:read` | View the audit log | `agency_admin`, `manager` |

(`tenant:configure` already existed from Phase 6 and covers branch/warehouse/cylinder-type/tenant-configuration/price-list CRUD.)

## Implementation Areas

| Area | Scope |
|---|---|
| A | Backend: `tenant.tenant` reconciliation (status/subscription_plan/primary_contact_email/country + lifecycle) |
| B | Backend: Branch & Warehouse aggregates, migrations, repositories |
| C | Backend: Cylinder Type aggregate |
| D | Backend: Tenant Configuration (historized) + `TenantConfigurationResolver` |
| E | Backend: Price List (historized) + `EffectivePriceResolver` |
| F | Backend: Feature flags — full system (`platform.feature_flag` + `tenant.feature_flag_override` + `FeatureFlagService`) |
| G | Backend: Staff user management (extends `application/identity/`) |
| H | Backend: Audit log read API (cursor-paginated) |
| I | Backend: API layer — `admin.py` router (26 endpoints), dependencies, schemas |
| J | Backend: Tests (RBAC, endpoint smoke) |
| K | Backend: Full validation gate |
| L | Frontend: Data-access additions (9 new services in `libs/shared/data-access`) |
| M | Frontend: Admin feature libraries (4 new Nx libs, 8 page components) |
| N | Frontend: Full validation gate |
| O | Cross-cutting: documentation close-out (this directory, `01-domain-model.md`, `03-database-schema.md`, `current_phase.md`, `12-current-status.md`) |

Full task-by-task breakdown: [TASKS.md](./TASKS.md). Outcome and verification numbers: [STATUS.md](./STATUS.md).

## Build & Verification Order

1. **A → B → C → D → E → F** — each is domain → migration → model → repository → unit/integration tests, `mypy`/`ruff`/`lint-imports` after each.
2. **G** (user management) — builds on Area B's now-real `branch_id` FK and extends the existing `identity` module.
3. **H** (audit log read) — independent, sequenced after for a clean single-threaded pass.
4. **I** (API layer) wiring everything above; **J** written alongside.
5. **K** — full backend gate.
6. OpenAPI regen → `L` → `M` → **N** full frontend gate.
7. Manual smoke: real backend (local Docker Postgres/Redis) + real Dashboard dev server, login as a seeded `agency_admin`, exercise a Branch CRUD round-trip and the audit-log viewer in a real browser.
8. **O** — documentation close-out.

## Explicitly Not Done (deferred, not oversight)

- WebSocket connection/subscription authorization — still its own fast-follow, unchanged from Phase 6.
- Mobile — Administration is Dashboard-only.
- Real invite-email delivery — Phase 14 (Notifications), same logging-only adapter Phase 6 established.
- Tenant self-service signup — remains an elevated/seed operation.
- New ADR — the feature-flag design and the aggregate-boundary divergence are documented in this plan, `STATUS.md`, and `01-domain-model.md` directly; nothing here was judged architecture-decision-worthy on its own.

## Bugs Found and Fixed During Implementation

Six genuine, previously-latent bugs, none Phase-7-specific in cause but all only surfaced by this phase's work:

1. **ORM `server_default` gaps** (`TenantModel`, `BranchModel`, `WarehouseModel`, `CylinderTypeModel`, `IdentityUserModel`) — a plain `session.add()` insert is the first thing to ever write these tables outside a migration/`SECURITY DEFINER` function; SQLAlchemy sends explicit `NULL` for any column without a mirrored `server_default=text(...)` on the mapped column, even though the migration's DDL has one.
2. **`Decimal` not JSON-serializable** in `AuditRecorder._jsonable()` — the first aggregate with a numeric/`Decimal` field (`CylinderType.weight_kg`) crashed on audit-row insertion.
3. **Test-authoring bug**: reusing one `UnitOfWork` instance across two commands in a test — `commit()` is idempotent-after-first-call, so the second command's changes never actually persisted. Fixed by giving each command its own fresh UoW.
4. **`SqlAlchemyStaffUserRepository.save()` silently dropping `password_hash`/`failed_login_count`/`locked_until`** — only branch_id/role/is_active were being persisted.
5. **Frontend eager-bundle AG Grid leak**: `ShellLayout` (eagerly loaded) importing `AppShellComponent` from `@lpg/shared/ui`'s barrel pulled the whole co-exported module graph — including `DataGridComponent` → `ag-grid-community` (~700KB) — into the initial bundle (1.38MB, over the 1MB hard budget). Fixed via a secondary Nx entry point (`libs/shared/ui/src/app-shell.ts`).
6. **Double `/api/v1` URL prefix** — pre-existing (not Phase-7-specific), only surfaced because this phase's manual browser verification was the first real login attempt against a live backend since `environment.ts` was last touched. `environment.apiUrl` already included `/api/v1`, and generated client functions' own `.PATH` constants also carry the full path.

A seventh issue — **AG Grid rendering at 0px height** across all 8 new admin pages (`DataGridComponent`'s `:host { block-size: 100%; }` collapsing when no ancestor gives it an explicit height) — was found during the same manual verification pass and fixed by wrapping every `<lpg-data-grid>` usage in a `.admin-page__grid { block-size: 400px; }` container, matching the pattern the component's own Storybook story already documented.
