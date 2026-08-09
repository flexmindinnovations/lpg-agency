# TASKS — Phase 4: Angular 22 Web Foundation

Legend: `[ ]` not started · `[~]` in progress · `[x]` complete and verified

---

## A — Brand Palette Refresh ✅ Complete 2026-08-09

- [x] **T-01** Reviewed product-owner-supplied design inspiration (sidebar/profile-menu UI patterns, four colour-palette pairings). Rejected the high-saturation palettes on concrete grounds (red/cherry-red collides with `color-status-danger` in a gas-safety context; lime/aureolin fail WCAG contrast as fills). Selected the Butter/Green pairing, confirmed by product owner.
- [x] **T-02** Computed WCAG contrast ratios for every candidate shade via a real luminance calculation (not eyeballed) before committing values. `forest-800` vs white = 10.15:1, `forest-400` vs `gray-950` = 7.92:1, highlight pairs 10.46:1 / 7.28:1 — all comfortably clear 4.5:1.
- [x] **T-03** New `forest`/`cream` primitives + updated `semantic.color.action.*`/`border.focus`/new `highlight.*` in `design-tokens/tokens.json`. High-contrast theme's `color-action-primary` deliberately kept on `hcBlue`, not switched to green — colour-vision-deficiency safety, documented in ADR-031.
  *Verify:* `node scripts/generate-tokens.mjs --check` clean; live-browser check of light/dark/high-contrast — PrimeNG buttons/tabs/dialog and the AG Grid wrapper all correctly re-themed with **zero component code changes**, confirming the token architecture.
- [x] **T-04** ADR-031 recorded; `docs/ui/10-color-system.md` §2–4 updated with new values and contrast notes.

## B — Layout Shell ✅ Complete 2026-08-09

- [x] **T-05** `AppShellComponent` (`libs/shared/ui/src/lib/app-shell/`) — collapsible sidebar, data-driven `NavGroup`/`NavItem` model, active-state highlight (using the new `color-highlight-*` tokens), PrimeNG `Tooltip` on collapsed icons, WCAG landmarks (skip link, `nav[aria-label]`, `main` with `tabindex="-1"`), `aria-current="page"` on the active link, `aria-expanded`/`aria-label` on the collapse toggle.
- [x] **T-06** Theme switcher moved from a top-bar `<select>` into a PrimeNG `p-menu` popup triggered from the sidebar footer, matching the profile-dropdown pattern from the design inspiration. All four theme options (System/Light/Dark/High contrast) verified live, including the currently-active option's `is-selected-theme` styling.
- [x] **T-07** `app.html`/`app.ts` rewritten to consume `AppShellComponent`; `navGroups` lists only "Home" — no invented business navigation.
- [x] **T-08** Fixed a real Jest/ESM transform gap surfaced by importing `primeng/menu`: its licence-check machinery pulls in `@primeui/license-manager` → `@noble/ed25519`/`@noble/hashes`, both ESM packages shipping `.js` (not `.mjs`) files that the existing `transformIgnorePatterns` (`.mjs`-only allowlist) didn't cover. Broadened the pattern in both `apps/dashboard/jest.config.cts` and `libs/shared/ui/jest.config.cts`.
- [x] **T-09** Raised the `dashboard` production bundle budget from 550kb to 660kb (actual: 646.40kb) — legitimate growth from `AppShellComponent` (used on every route, so correctly part of the eager bundle) pulling in `primeng/menu`/`primeng/badge`, not scope creep.
  *Verify:* `nx build dashboard` clean, no budget warning. `nx run-many -t lint test build --all` — 6/6 projects green, including updated `app.spec.ts` assertions for the new shell markup and theme-menu behaviour. `prettier --check` clean. Live-browser verified: collapse/expand, active-item highlight, theme menu (all 3 themes), zero console errors.

## C — Storybook 🔶 Configured, build blocked (DW-24)

- [x] **T-10** Configured Storybook for the Nx Angular workspace (`@nx/storybook` generator), `libs/shared/ui/.storybook/main.ts`/`preview.ts` (loads real `tokens.css` + the actual `LpgPrimeNgPreset` via `applicationConfig`, so stories render through the same token cascade the app uses, never a Storybook-only stylesheet).
- [x] **T-11** Stories written: `app-shell.component.stories.ts` (a thin host component binding `navGroups`, since `AppShellComponent` needs content projection + a router context), `data-grid.component.stories.ts` (three variants: default, single-selection, loading — with an explicit height wrapper, since AG Grid sizes to its host).
- [ ] **T-12 — blocked, DW-24.** `nx build-storybook shared-ui` fails. Root cause is a chain of upstream compatibility gaps between Angular 22, Storybook 10.5.7, and Nx 23.1.1 — a combination that appears to not yet be a validated, stable combination in the ecosystem (all three are recent releases):
  1. Storybook 10.x's Angular integration dropped support for the CLI-direct invocation `@nx/storybook`'s generator produces by default; requires an explicit Angular CLI builder (`@storybook/angular:build-storybook`/`start-storybook`) with a `browserTarget`. **Fixed** — explicit targets added to `libs/shared/ui/project.json` pointing at `dashboard:build:development`.
  2. `@storybook/angular@9.0.6` (the version `@nx/storybook@23.1.1` was actually tested against, per its own devDependency pin) does not support Angular 22 at all (`@angular/core: '>=18.0.0 < 21.0.0'`) — ruled out as an alternative.
  3. `@angular-devkit/build-angular@22.1.3` (required as a peer once using the real Angular builder) bundles its own nested `webpack@5.109.2`, distinct from the top-level `webpack@5.105.2` Storybook's own builder resolved — a dual-package-instance hazard causing `Cannot read properties of undefined (reading 'tap')`. **Fixed** — `"overrides": { "webpack": "5.109.2" }` added to `package.json` to force a single instance.
  4. After fixing (1)–(3), the build now fails differently: `SB_BUILDER-WEBPACK5_0003 (WebpackCompilationError)`, with webpack reporting several `Conflict: Multiple assets emit different content to the same filename` errors on `*.iframe.bundle.js.map` files — consistent with two webpack compilations running against the same output directory. Not yet root-caused. Recorded as **DW-24**, not silently left broken or hidden: the configuration/stories are real and correct groundwork, but `nx build-storybook`/`nx storybook` do not currently produce a working build. Revisit when the Storybook/Angular ecosystem catches up to Angular 22, or with a dedicated investigation session — not blocking the rest of Phase 4.

## D — Playwright Execution (T-34) ✅ Complete 2026-08-09

- [x] **T-12** Installed Playwright browser binaries (`npx playwright install`) — chromium was already present from earlier tooling use; firefox and webkit downloaded fresh.
- [x] **T-13** Rewrote `apps/dashboard-e2e/src/example.spec.ts` — the generated placeholder asserted an `<h1>` containing "Welcome", which this app never had. Now 4 real smoke tests against the actual shell: heading renders, sidebar collapse/expand toggles the brand label's visibility, the theme menu switches to dark mode and sets `data-theme`, and the page loads with zero console errors.
  *Found and fixed a real Nx 23 bug along the way:* `nx e2e dashboard-e2e` failed with "Recursive task invocation detected" — Nx's new cross-process task-invocation guard (tracks task IDs in a local DB keyed by root PID) treats Playwright's own documented `webServer.command: 'npx nx run dashboard:serve'` pattern as a false-positive loop, because the spawned process inherits the parent `nx e2e` invocation's root-PID lineage and the target ID collides. Fixed by setting `NX_INVOCATION_ROOT_PID` to the Playwright config process's own PID in `webServer.env`, giving the nested spawn an independent lineage — confirmed stable across repeated runs.
  *Verify:* `nx e2e dashboard-e2e` — **12/12 passed** (4 tests × 3 browsers: chromium, firefox, webkit), run twice consecutively to confirm stability.

## E — axe-core Accessibility Gate ✅ Complete 2026-08-09

- [x] **T-14** `@axe-core/playwright` installed; `apps/dashboard-e2e/src/accessibility.spec.ts` scans the home page (light/dark/high-contrast themes, collapsed sidebar, open dialog) against `wcag2a`/`wcag2aa`/`wcag21aa`/`wcag22aa` tags, asserting zero violations.
  **Found and fixed three real accessibility bugs**, none caught by the earlier manual verification pass:
  1. The demo breadcrumb's icon-only "Home" crumb (`pi pi-home`, no text) had no accessible name — fixed with `p-breadcrumb`'s `homeAriaLabel` input.
  2. The dialog's icon-only close button had no accessible name — fixed with `p-dialog`'s `closeAriaLabel` input.
  3. `AppShellComponent`'s own collapsed-sidebar nav links relied on `pTooltip` for the label, which is a visual hover affordance, not an accessible name — fixed with an explicit `[attr.aria-label]` bound to the item label when collapsed.
  *Verify:* `nx e2e dashboard-e2e` — 27/27 passed (9 tests × 3 browsers), confirmed clean on two consecutive full runs.

## F — Generated API Client ✅ Complete 2026-08-09

- [x] **T-15** ADR-032 records the decision: **`ng-openapi-gen`**. Deciding factor — its generated functions accept an injected `HttpClient` and call `http.request(...)` directly, so generated calls flow through the same `correlationIdInterceptor`/`problemDetailsInterceptor` pipeline as every hand-written call, unlike generators that ship their own `fetch`/`axios` client (would silently bypass both).
- [x] **T-16** Scaffolded against the committed spec (`backend/openapi/openapi.json`, only `/health/live` + `/health/ready` exist today): `frontend/ng-openapi-gen.json` config, `npm run generate:api-client` script, output at `libs/shared/data-access/src/lib/generated/` (re-exported from the library's public `index.ts`), excluded from ESLint/Prettier (generated, never hand-edited, matching the existing `tokens.css`/`tokens.ts` precedent). **Deliberately not wired into `app.config.ts`** — `provideApiConfiguration(rootUrl)` needs a real backend base URL, and this codebase has no established frontend environment-config pattern yet; inventing one for a client with no consumer would be guessing at deployment architecture. That wiring belongs with the phase that makes the first real API call.
  *Verify:* `nx run-many -t lint test build --all` — 6/6 projects green with the generated code present. `prettier --check` clean.

## G — Verification & Close-Out ✅ Complete 2026-08-09

- [x] **T-17** Full frontend verification: `nx run-many -t lint test build --all` (6/6 green), `prettier --check` (clean), `node scripts/generate-tokens.mjs --check` (clean), `nx e2e dashboard-e2e` (27/27 passed, chromium/firefox/webkit, confirmed on repeated runs), live-browser check across all three themes.
- [x] **T-18** `planning/current_phase.md`, `knowledge/02-tech-stack.md`, `knowledge/12-current-status.md` updated. Phase 4 marked complete with DW-24 (Storybook build) recorded as the one open, non-blocking item.
