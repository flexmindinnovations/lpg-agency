# 67 — Module visibility (super admin shows/hides modules per agency)

## Goal
A super admin can switch **AI Command Center**, **Scales** and **Cylinder Units** off for an agency.
Off means: hidden in the dashboard sidebar, the URL redirects home, and the API refuses the module's calls.

## Decisions (owner, 2026-11-24)
- Controlled by the **super admin per agency** (Platform Console). The agency cannot change it.
- **Hide and block** — not cosmetic only.
- Every module is **on by default**; a row exists only where a super admin has switched one.

## Design
- Fixed catalog in code: `lpg.domain.license.modules.TOGGLEABLE_MODULES`.
- Storage: `platform.tenant_module_setting` (tenant-scoped, RLS) — independent of licences, so it works
  for agencies that have no licence issued.
- Platform API: `GET/PUT /platform/agencies/{tenant_id}/modules` (`license:manage_platform`, live-checked).
- Tenant API: `GET /admin/modules` — the caller's agency modules, for the sidebar and route guard.
- Enforcement: `require_module(key)` router dependency on `/ai`, `/scales`, `/cylinder-units` → 403 `MODULE_DISABLED`.
- Dashboard: `ModuleAccessService`, sidebar filter, `moduleGuard`, Modules drawer on the Customers (agencies) page.

## Out of scope
Package/tier bundles, licence-expiry behaviour, the mobile apps' own module hiding (they receive 403 from the API).
