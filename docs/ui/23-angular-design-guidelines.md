# 23 — Angular Design Guidelines

## Purpose
Creates Angular 22 UI guidelines: standalone components, Signals, component architecture, container vs presentational components, control flow, deferred loading, Angular Material, Angular CDK, Tailwind CSS, Storybook, accessibility — the frontend realization of this design system for the Agency Web Dashboard.

## 1. Standalone Components
Every component is standalone (no NgModules), matching Angular 22's default and the approved Enterprise Architecture's Nx workspace structure (docs/architecture/04-frontend-architecture.md). Shared design-system components live in a dedicated shared UI library, imported directly by feature libraries.

## 2. Signals
- Signals are the default for local/component state, form state, and derived/computed values (computed for anything derived from another Signal, never manually re-synchronized).
- RxJS is reserved specifically for asynchronous streams per the architecture guidelines: HTTP calls, real-time status updates (Live Delivery Tracking), debounced search input — RxJS streams are converted to Signals at the boundary wherever the result feeds a template, keeping templates Signal-based throughout.
- Component inputs/outputs use the Signal-based input/output APIs, not the legacy decorator-based approach.

## 3. Component Architecture — Container vs Presentational
- Presentational components (in the shared UI library, `12-component-library.md`): pure, receive data via input, emit via output, no direct service/store injection, fully Storybook-documented.
- Container components (in feature libraries): own state/data-fetching (via injected services/stores), compose presentational components, contain no styling of their own beyond layout composition.
- This split is non-negotiable for any component beyond the most trivial — it is what keeps presentational components genuinely reusable and Storybook-testable in isolation.

## 4. Control Flow
Uses Angular's native control-flow syntax exclusively — never the legacy structural directives, consistent with Angular 22's recommended direction and improving both readability and built-in tracking performance without manual trackBy functions.

## 5. Deferred Loading
Deferred loading blocks are used for: below-the-fold widget content on the Home/KPI Overview screen (`06-dashboard-layout.md` section 5's Attention Row, deferred until the KPI row above has rendered), heavy components not needed on initial paint (Chart components, the Route Planning Board's Map widget), and any Dialog/Drawer's content (deferred until first opened, never bundled into the initial page load). Every deferred block specifies an explicit loading (skeleton, matching `07-wireframe-specifications.md` loading-state patterns) and placeholder template — never a blank gap while deferred content loads.

## 6. Angular Material
Used as the base primitive layer for interaction patterns Material already solves well and accessibly: Dialog/Overlay (via CDK, wrapped by the shared Drawer/Dialog components), form field structure, Menu. Material's visual styling is fully overridden by the design token system (`09-design-tokens.md`) — Material provides behavior/accessibility scaffolding, never its default visual language, which would conflict with the platform's Linear/Stripe-benchmarked visual identity.

## 7. Angular CDK
Used directly (without Material's styled layer) for: Overlay positioning (Command Palette, Popover, Tooltip), accessibility utilities (focus trap, live announcer for the aria-live patterns throughout `17-accessibility.md`), key-manager utilities for the Data Grid's custom keyboard navigation (`14-data-grid-guidelines.md` section 9), and Virtual Scrolling primitives where AG Grid's own virtualization isn't the right fit (non-grid long lists, e.g. the Command Palette's result list).

## 8. Tailwind CSS v4
Utility classes consumed via the token-mapped Tailwind theme (`09-design-tokens.md` section 10) — never arbitrary-value utilities with raw hex colors anywhere in the codebase, enforced via a lint rule. Tailwind handles layout/spacing utility application; component-specific styling beyond simple utilities lives in the component's own scoped styles referencing CSS custom properties directly.

## 9. Storybook
Every shared UI library component has a corresponding Storybook story file covering every state defined in its `13-component-specifications.md` entry, plus an accessibility-addon-validated story. Storybook serves as both the living component documentation (for designers/AI agents referencing `25-lovable-prompts.md`) and the primary visual regression test surface, integrated into CI.

## 10. Accessibility (Angular-Specific)
- The CDK live announcer is the sole mechanism for aria-live announcements — never manual DOM manipulation of live regions.
- Route transitions use Angular Router's navigation events to move focus to the new page's primary heading (`17-accessibility.md` section 4), implemented once as a router-level service, not per-route.
- Every custom component (Data Grid, Command Palette) implements full keyboard navigation via CDK's key-manager utilities rather than ad-hoc keydown handlers, ensuring consistent, tested keyboard behavior across all custom interactive components.

## Best Practices
- Jest for unit tests, Playwright for E2E and critical-flow accessibility testing (axe-core integration) — matching the approved technology stack.
- No component in the shared UI library has a dependency on any specific feature library — dependencies only ever point from feature libraries toward shared, never the reverse (enforced via Nx module-boundary lint rules, per the approved Enterprise Architecture).

## Risks
- Deferred-loading-block misuse (deferring content that's actually needed for the primary task, causing a jarring pop-in) — mitigated by design review explicitly confirming which content is genuinely below-the-fold/non-critical before a defer boundary is added.

## Alternatives Considered
- Classic NgRx (actions/reducers/effects) for all state — rejected in favor of Signals-first state management with NgRx SignalStore reserved for genuinely complex shared feature state, consistent with Angular's own architectural direction and reducing boilerplate.

## Future Scalability
- The strict container/presentational split and shared-library-only presentational components mean a future design refresh only requires updating the shared library, with container components and business logic completely unaffected.
