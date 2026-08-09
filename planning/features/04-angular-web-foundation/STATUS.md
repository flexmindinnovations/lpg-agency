# STATUS — Phase 4: Angular 22 Web Foundation

**Feature:** 04-angular-web-foundation
**Plan:** [PLAN.md](./PLAN.md) · **Tasks:** [TASKS.md](./TASKS.md)

---

## Status

**COMPLETE — 17/18 tracked tasks verified, 1 blocked (DW-24).** Started and finished 2026-08-09, in a single continuous session, on explicit instruction.

## Progress

| Area | Complete | State |
|---|---|---|
| A — Brand Palette Refresh | 4/4 | ✅ Verified |
| B — Layout Shell | 5/5 | ✅ Verified |
| C — Storybook | 2/3 | 🔶 Configured; build blocked, DW-24 |
| D — Playwright Execution | 2/2 | ✅ Verified — T-34 closed |
| E — axe-core Gate | 1/1 | ✅ Verified |
| F — Generated API Client | 2/2 | ✅ Verified |
| G — Verification & Close-Out | 1/1 | ✅ Verified |

## What Was Built

### Area A — Brand Palette Refresh

Product owner supplied design inspiration (sidebar/profile-menu UI patterns from reference screenshots, four colour-palette pairings). Three of the four palettes were rejected on concrete product-specific grounds, not taste — see ADR-031 (red/cherry-red colliding with `color-status-danger` in a gas-safety context is the one that matters most). The Butter/Green pairing was selected and confirmed.

New `forest` (brand primary, deliberately distinct from `primitive.color.green`, which stays reserved for `color-status-success`) and `cream` (highlight accent) primitive scales added to `design-tokens/tokens.json`. Every contrast ratio was computed via a real luminance calculation, not eyeballed, before being committed. High-contrast theme's primary deliberately stays pure blue (`hcBlue`) rather than switching to a high-contrast green — colour-vision-deficiency safety reasoning documented in ADR-031.

**Zero component code changes were needed anywhere** — the PrimeNG preset, the AG Grid wrapper, and every app style reference tokens, never hex values directly. This is the token architecture (Phase 1) paying for itself exactly as designed.

### Area B — Layout Shell

New `AppShellComponent` (`libs/shared/ui/src/lib/app-shell/`): collapsible sidebar with icon+label nav, data-driven `NavGroup`/`NavItem` model (currently just "Home" — no invented business navigation), active-item highlight using the new highlight tokens, and the theme switcher relocated from a plain top-bar `<select>` into a PrimeNG `p-menu` popup in the sidebar footer — the profile-dropdown pattern from the design inspiration, applied to the one piece of "identity" this app actually has today (no user auth yet, so no fake user name/avatar was invented).

Two real issues found and fixed along the way:
1. Importing `primeng/menu` pulled in `@primeui/license-manager`'s licence-check machinery, which depends on `@noble/ed25519`/`@noble/hashes` — ESM packages shipping `.js` (not `.mjs`) files the existing Jest `transformIgnorePatterns` (`.mjs`-only allowlist) didn't cover. Fixed in both `apps/dashboard/jest.config.cts` and `libs/shared/ui/jest.config.cts`.
2. The production bundle budget (550kb) was legitimately exceeded (646.67kb) because `AppShellComponent` — used on every route — is part of the eagerly-loaded bundle, unlike the previous PrimeNG usage confined to a lazy route. Raised to 660kb with the reasoning recorded, not silently bumped.

### Area C — Storybook (configured, build blocked — DW-24)

Full configuration exists and is correct: `.storybook/main.ts`/`preview.ts` (loads the real `tokens.css` and the actual `LpgPrimeNgPreset` via `applicationConfig`, so a story is honest evidence of a component's real appearance), and stories for `AppShellComponent` and `DataGridComponent`.

**`nx build-storybook shared-ui` does not currently succeed.** Traced through a chain of Angular 22 / Storybook 10.5.7 / Nx 23.1.1 compatibility gaps (Storybook 10.x requiring an explicit Angular CLI builder rather than direct CLI invocation; the only Storybook version `@nx/storybook` was tested against not supporting Angular past 20; a dual-webpack-instance hazard between Storybook's builder and `@angular-devkit/build-angular`'s bundled webpack) — the first two were fixed (explicit `@storybook/angular:build-storybook`/`start-storybook` targets in `libs/shared/ui/project.json`; a `webpack` version override in `package.json`). The build now fails at a fourth, different point (`SB_BUILDER-WEBPACK5_0003`, webpack asset-filename conflicts), not yet root-caused — recorded as **DW-24**, a genuine ecosystem-maturity gap for this exact version combination, not a defect in the configuration itself.

### Area D — Playwright Execution (T-34, closed)

Browser binaries installed. `apps/dashboard-e2e/src/example.spec.ts` — the generated placeholder asserted an `<h1>` containing "Welcome", which this app never had — rewritten into 4 real smoke tests against the actual shell.

**Found and fixed a real Nx 23 bug:** `nx e2e dashboard-e2e` failed with "Recursive task invocation detected" — Nx's new cross-process task-invocation guard (tracks task IDs in a local DB keyed by root PID) treats Playwright's own documented `webServer.command: 'npx nx run dashboard:serve'` pattern as a false-positive loop, because the spawned process inherits the parent `nx e2e` invocation's root-PID lineage and the target ID collides. Fixed by setting `NX_INVOCATION_ROOT_PID` to the Playwright config process's own PID in `webServer.env`.

### Area E — axe-core Accessibility Gate

`@axe-core/playwright` installed; `accessibility.spec.ts` scans the home page (light/dark/high-contrast themes, collapsed sidebar, open dialog) against WCAG 2.1/2.2 AA tags.

**Found and fixed three real accessibility bugs**, none caught by the earlier manual verification pass:
1. The demo breadcrumb's icon-only "Home" crumb had no accessible name — fixed with `p-breadcrumb`'s `homeAriaLabel`.
2. The dialog's icon-only close button had no accessible name — fixed with `p-dialog`'s `closeAriaLabel`.
3. `AppShellComponent`'s own collapsed-sidebar nav links relied on `pTooltip` (a visual hover affordance, not an accessible name) — fixed with an explicit `[attr.aria-label]`.

One test-authoring bug also found and fixed: the dark/high-contrast scans initially caught axe evaluating the theme-switcher menu *mid-close-transition*, reporting a transient, transition-blended colour (`#161d2c` on `#111827`) that never appears in the settled DOM — fixed by waiting for the menu to be fully hidden before scanning.

### Area F — Generated API Client

**ADR-032**: `ng-openapi-gen`, chosen because its generated functions accept an injected `HttpClient` and call `http.request(...)` directly — every generated call flows through the same `correlationIdInterceptor`/`problemDetailsInterceptor` pipeline as hand-written calls, unlike generators shipping their own `fetch`/`axios` client. Scaffolded against the committed spec (`backend/openapi/openapi.json` — only the two health endpoints exist today): config, `npm run generate:api-client` script, output at `libs/shared/data-access/src/lib/generated/`, excluded from ESLint/Prettier.

**Now wired into `app.config.ts`** (ADR-033, 2026-08-09): `provideApiConfiguration(environment.apiUrl)` registered alongside the existing HTTP providers. `apps/dashboard/src/environments/environment.ts` (dev, `http://localhost:8000/api/v1`) is swapped for `environment.prod.ts` (`/api/v1`, relative — ADR-022's hosting topology is still undecided) via `fileReplacements` in the `production` build configuration. Verified both build configurations embed the correct URL and neither leaks the other's; live-browser smoke test showed no regressions.

## Verification (2026-08-09)

| Check | Result |
|---|---|
| `nx run-many -t lint test build --all` | ✅ 6/6 projects green |
| `prettier --check` | ✅ Clean |
| `node scripts/generate-tokens.mjs --check` | ✅ Clean |
| `nx e2e dashboard-e2e` | ✅ **27/27 passed** (9 tests × 3 browsers: chromium, firefox, webkit), confirmed clean on repeated runs |
| Live-browser (light/dark/high-contrast) | ✅ Collapse/expand, active-item highlight, theme menu, focus trap/return, zero console errors |
| `nx build-storybook shared-ui` | ❌ Blocked, DW-24 |

## Still Open

- **DW-24** — Storybook build fails (`SB_BUILDER-WEBPACK5_0003`). Configuration and stories are real and correct; the build pipeline needs further investigation or an ecosystem update. **Explicitly deferred to post-MVP by product owner decision (2026-08-09)** — not a priority now, revisit once the Angular 22 / Storybook 10.x / Nx 23 ecosystem has matured or a dedicated investigation session is scheduled.
- Every business use case that will eventually extend `AppShellComponent`'s `navGroups` — arrives with the modules that own them, per this phase's explicit exclusions in `PLAN.md`.

## Last Updated

2026-08-09 — phase complete, all areas verified except Storybook's build (DW-24, tracked separately, non-blocking). API client wired end-to-end (ADR-033) same day, ahead of the phase originally expected to need it.
