# Status: Dashboard Settings Area

**Status:** Built, merged and deployed 2026-10-16 (PR #5 `9bff24c` → merge `4d1a9c4`; PR #6 `98e530a` → merge `8976567`), and checked in the browser on the deployed site with real data (agency admin session).

## Verified (gates re-run, output seen)

| Gate | Result |
|---|---|
| `nx test` dashboard / shared-ui / shared-data-access | 27 / 70 / 53 passed |
| `nx lint` (affected projects) | exit 0; the only warnings are pre-existing `no-explicit-any` / unused-var in unrelated files |
| `prettier --check` on the touched files | clean |
| `nx build dashboard` | succeeds; initial bundle 710 kB against a 700 kB budget (warning only; was already over, about +0.9 kB from this change) |
| Pull request CI (`validate`, two jobs) | both passed on PR #5 and PR #6 |
| Deploy run 38891391905 (PR #5) and 38900287128 (PR #6) | every stage passed (gates, both image builds, deploy) |
| Droplet after deploy | backend, worker and web containers on the merge-commit image; backend healthy; `LPG_ENVIRONMENT` still `uat`; the new `/settings/...` routes are in the served bundle |
| Browser, stub API with a fake session | agency admin sees both groups and six links; a dispatcher sees Account only and is refused `/settings/license`; legacy URLs redirect; License and Linked Devices highlight separately; the mobile layout does not scroll the page sideways; cards are flat in Settings and unchanged on `/design-system`; the user menu lists only the theme options and Sign Out |
| `GET /admin/tenant` on the droplet | returns the agency code for the agency admin |
| **Deployed site** (https://lpg.vitessetec.com, signed in as an agency admin) | All six sections render with real data and no error banner: My Profile, Agency (name, code `DEV123456`, status, plan, contact, country), Configuration (grid with rows), Feature Flags (empty state: no flags exist yet), License (active, key prefix, activation and expiry dates), Linked Devices (empty state). Cards are flat on My Profile, Agency, License and all three TDT Rating section cards. The Configuration page's TDT link goes to `/settings/configuration/tdt-rating` (breadcrumb `Settings > Configuration > TDT Rating`, Configuration stays highlighted) and its back button returns to `/settings/configuration`. |
| Deployed site, legacy URLs (fresh page loads and in-app) | `/profile`, `/admin/license`, `/admin/license/devices`, `/admin/tenant-config`, `/admin/tenant-config/tdt-rating` and `/admin/feature-flags` each land on their `/settings/...` equivalent; `/settings` lands on `/settings/account` |
| Deployed site, shell | sidebar has the single Settings item and none of the four old entries; the user menu lists System, Light, Dark, High contrast and Sign Out (no My Profile); no console errors; every request in the sampled network log returned 200 |

## Not verified

- `apps/dashboard-e2e/src/profile-menu.spec.ts`: updated to the new menu, not run (it needs a signed-in session). It already referenced a "Design system" menu entry that was removed earlier, so it was out of date before this change.
- A tenant whose license is blocked, using the Settings nav.

## Found along the way

- **Production accounts differ from the runbook.** `infrastructure/deploy/DEPLOY.md` lists only the bootstrap `super_admin` as an account, but the droplet database also holds the demo-seed users for tenant `DEV123456`. Decide whether to deactivate them before real use, and correct the runbook's accounts inventory.
- `/health/ready` returns 503 on the droplet because object storage is not configured (Postgres, Redis and the job queue are healthy). Unchanged by this work.

Design: [PLAN.md](./PLAN.md). Tasks: [TASKS.md](./TASKS.md). Decision: ADR-070.
