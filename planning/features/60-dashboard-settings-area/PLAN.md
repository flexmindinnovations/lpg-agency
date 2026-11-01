# Plan: Dashboard Settings Area

> Renumbered 2026-11-01: first written as feature 34 / ADR-052, numbers since taken by the mobile UI overhaul. Written after the fact (2026-10-16): the work was done in three small pull requests in one session and this folder records the decisions. Frontend only; no backend or API change.

## Goal

Drivers and customers must type the **agency code** (the tenant slug) to sign in to the mobile apps, but no dashboard screen showed it to an agency admin. Fixing that exposed a wider problem: four agency-wide admin pages (Tenant Config, Feature Flags, License, Linked Devices) each had their own sidebar entry and `/admin/...` route, while the personal "My Profile" page lived only in the user menu.

## Decision (ADR-070)

One **Settings** area at `/settings`, with a section nav in two groups:

| Group | Section | Route | Permission |
|---|---|---|---|
| Account | My Profile | `/settings/account` | none (every role) |
| Agency | Agency | `/settings/agency` | `tenant:read` |
| Agency | Configuration (+ TDT Rating) | `/settings/configuration[/tdt-rating]` | `tenant:configure` |
| Agency | Feature Flags | `/settings/feature-flags` | `feature_flags:manage_tenant` |
| Agency | License | `/settings/license` | `license:manage_tenant` |
| Agency | Linked Devices | `/settings/license/devices` | `license:manage_tenant` |

Personal data stays out of the agency group and vice versa: Account is open to every role, Agency sections are tenant-wide and permission-gated.

## Design

- `SettingsShell` (`apps/dashboard/src/app/settings/`) supplies only the frame: a grouped section nav beside a `<router-outlet>`; on narrow screens the nav becomes a horizontally scrolling row. It hides a section the user lacks the permission for; the router still refuses it independently (each section keeps its own `permissionGuard`).
- Section definitions live in `settings-sections.ts` and feed both the nav and the command palette, so each section is still findable by name with Ctrl+K.
- Sidebar: the four admin entries become one always-visible **Settings** item (Account is open to every role).
- Old URLs (`/profile`, `/admin/tenant-config[/tdt-rating]`, `/admin/feature-flags`, `/admin/license[/devices]`) redirect to the new ones so bookmarks and shared links keep working.
- `license.guard` exempts `/settings/license*` (was `/admin/license*`) so a blocked tenant can still reach activation; `LicenseRequired` links there.
- New read-only **Agency** section (`GET /admin/tenant`) shows name, agency code with its sign-in hint, status, plan, contact and country. The code was first added to Profile (PR #5) and moved here.
- "My Profile" is removed from the user menu; Settings > Account replaces it.
- Settings cards are flat: `lpg-section-card` and the TDT section card read optional `--card-border` / `--card-shadow` custom properties; the Settings content area sets both to `none`. Unset (everywhere else), cards are unchanged.

## Testing

- Unit: nav groups/links by permission (admin, no permissions, partial); active-link state (License vs Linked Devices); agency page ready/error; Profile; route-guard invariants and legacy redirects (`app.spec.ts`); the user menu's contents.
- Browser, against a stub API with a fake session: both permission shapes, legacy redirects, mobile layout, flat cards inside Settings vs unchanged cards on `/design-system`, user menu items.

## Out of scope

- Editing agency details (the page is read-only; no self-service edit endpoint beyond tenant rename in Tenant Config).
- Moving Branches, Warehouses, Cylinder Types, Pricing, Users & Roles, Employees or Audit Log: those are operational master data and stay in the sidebar.
