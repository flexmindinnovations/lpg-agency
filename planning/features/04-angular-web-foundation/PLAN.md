# PLAN — Phase 4: Angular 22 Web Foundation

**Feature ID:** 04-angular-web-foundation
**Phase:** Phase 4
**Type:** Foundation — frontend infrastructure and design system, no business domain
**Created:** 2026-08-09
**Depends on:** [Phase 1 — Repository / Development Foundation](../01-repository-foundation/STATUS.md) ✅ Complete, [Phase 3 — Shared Infrastructure](../03-shared-infrastructure/STATUS.md) ✅ Complete

---

## Objective

Close out `docs/implementation/roadmap.md`'s Phase 4 line item: *"Nx workspace, design tokens, theme system, shared UI library (PrimeNG-based), AG Grid Community wrapper, layout shell, interceptors, generated API client, Storybook, Jest, Playwright, axe-core gate."*

Most of this list was already delivered ahead of schedule — Nx workspace, design tokens, theme system, the PrimeNG-based shared UI library, and the AG Grid wrapper were built in Phase 1 and the same-day PrimeNG close-out (T-68). **Phase 4's actual remaining scope is narrower**: a design-token palette refresh (product-owner-directed), the layout shell's collapsible-sidebar upgrade, Storybook, Playwright execution, an axe-core accessibility gate, and a decision + scaffold for the generated API client.

**No business feature is implemented.** No Customer, Order, Inventory, Delivery, Accounting screens. The sidebar navigation model is data-driven and currently lists only "Home" — extending it is deliberately left to the phases that add real routes.

---

## Scope

### Include

| Area | Deliverable |
|---|---|
| Brand palette refresh | New `forest` (brand primary) and `cream` (highlight accent) primitive scales in `design-tokens/tokens.json`, replacing blue as `color-action-primary`; WCAG AA contrast verified by computation, not eyeballed. Recorded as ADR-031. |
| Layout shell | `AppShellComponent` (`libs/shared/ui`) — collapsible sidebar (icon+label, data-driven `NavGroup[]`/`NavItem[]`), active-state highlight, theme switcher relocated into a PrimeNG `p-menu` popup in the sidebar footer (replacing the old top-bar `<select>`), full keyboard/landmark accessibility retained. |
| Storybook | Configured for the Nx Angular workspace; stories for existing shared UI components (`AppShellComponent`, `DataGridComponent`). |
| Playwright execution | Browser binaries installed, existing e2e smoke test actually run — closes T-34 (blocked since Phase 1). |
| axe-core gate | Automated WCAG 2.2 AA checking wired into the e2e suite. |
| Generated API client | Decision recorded (ADR) and tooling scaffolded against the committed OpenAPI spec — necessarily thin today, since only health-check endpoints exist until Phase 6+. |

### Exclude — explicitly out of scope

Authentication · Customer/Inventory/Order/Delivery/Accounting/Complaint/Reporting screens · any business nav item beyond "Home" · a production API client consuming business endpoints that don't exist yet.

---

## Architectural Basis

| Decision | Source |
|---|---|
| Brand colour: deep forest green, not blue | ADR-031 |
| PrimeNG as primary component library, token-driven | ADR-028, ADR-020 amendment, T-68 |
| Nx `enforce-module-boundaries`, `type:ui` → `type:design-tokens` dependency allowed | ADR-018, `frontend/eslint.config.mjs` |
| Code-first OpenAPI, generated spec as frozen client contract | ADR-026 |
| WCAG 2.2 AA (D-35) | `docs/architecture/11-accessibility-strategy.md` |
