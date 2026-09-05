# Plan: Dashboard Enterprise UX Overhaul — Fluent Glass Design System

**Phase:** 29
**Status:** Stages 0–3 + 5–8 done · Stage 4 core done (4b pending) · 2026-09-05 · Stages 9–10 pending
**Type:** Full visual redesign + motion system + one new feature (command
palette). No backend/data-model changes.

---

## Context

Built from a full audit of `frontend/apps/dashboard` + `frontend/libs/*`
(Angular 22, standalone/zoneless, 100% lazy-loaded per ADR-018, PrimeNG ^22
on a custom Aura preset, Tailwind v4) plus a reference document
(`GAS Fluent Glass Enterprise Design System Prompt.md`, attached by the user
alongside a screenshot): a dark-first, Windows 11 Fluent 2 / Mica / Acrylic
inspired enterprise design language — deliberately restrained (the doc
itself warns against neon, excessive blur, and gaming aesthetics).

**Audit findings this phase addresses:**

1. **Zero route-transition or micro-interaction animation.**
   `@angular/animations`'s DSL (`trigger`/`animate`/`transition`) has zero
   usage anywhere; `provideAnimationsAsync()` exists solely to power
   PrimeNG's own overlay animations. Navigation between routes is a hard cut.
2. **No shared UI-primitive components** — `PageHeader`, `EmptyState`,
   loading skeletons, stat/KPI cards, and section panels are all
   reimplemented per-page as raw CSS classes (`.page-header`, `.empty-state`,
   `.kpi-card`, `.panel`) rather than components. `home.ts` alone hand-rolls
   ~200 lines of this.
3. **No loading skeletons anywhere** — `p-skeleton` has zero usage; loading
   states are "—" placeholder text or a bare "Loading…" string.
   `DataGridComponent` even has an unused `loading` input.
4. **Forms are CSS-class-only** (`.form-group`/`.field-hint`/`.field-error`),
   no shared form-field component, no floating labels.
5. **Two competing table systems**: the sanctioned `lpg-data-grid` (AG Grid,
   ADR-020/028, used in 9 feature lists) vs. raw `p-table` (used in all 4
   `libs/reporting` views, with none of the sort/filter/pagination the AG
   Grid wrapper gives everywhere else).
6. **Minor hygiene**: `@angular/material` is a fully unused dependency; one
   deprecated `.toPromise()` call
   (`customer-onboarding-wizard.component.ts`); one mixed
   reactive/template-driven form binding (`order-queue.html`'s
   `CustomerAutocomplete`); one component-selector prefix inconsistency
   (`lib-notification-drawer` vs. the `lpg-` convention everywhere else).

**Decisions locked in with the user:**

1. **Dark becomes the default** theme for new sessions. Light and the
   existing WCAG **high-contrast** mode (a real asset the reference doc
   doesn't cover at all) stay fully supported in the switcher.
2. **Adopt the reference's exact palette** (neutral 0–950 scale, primary
   blue 400–700, accent sky-blue, semantic success/warning/danger/info) as
   the new primitive token values — not a reinterpretation of the existing
   gas-blue/flame-orange brand. The flame-mark SVG logo stays as a one-off
   decorative element (iconography, not a token).
3. **Command palette (Ctrl/Cmd+K) is in scope** as its own stage, bounded to
   navigation + customer search + 2 quick-create actions.

**Strategy — re-skin via tokens, not a rewrite.**
`libs/shared/design-tokens` already has the exact seams this needs: a
generated `tokens.css` (source `tokens.json` + `generate-tokens.mjs`), a
`ThemeService` with light/dark/high-contrast/system, and a PrimeNG preset
built on `definePreset(Aura, {...})`. This phase changes token **values**
and adds new **material** tokens (Mica/Acrylic) — the mechanism (components
read `var(--...)`, never literal colors) stays exactly as-is and is why this
is affordable.

Icon system: **no library swap.** PrimeIcons are already single-weight
outline glyphs (confirmed against the doc's "outline based, simple,
consistent stroke width" rule) — this phase standardizes *sizing*
conventions (18px nav / 16px button / 20–24px feature) rather than replacing
~40+ icon call sites.

---

## Stage 0 — Design tokens: Fluent Glass palette + materials

- **`libs/shared/design-tokens/src/lib/tokens.json`** (source of truth —
  never hand-edit generated CSS): replace primitive color scales with the
  reference's exact values — neutral 0–950, primary 400–700 (expanded to a
  full 50–950 scale via the existing `tokenScale()` `color-mix()` helper so
  it still plugs into PrimeUIX's `primary`/`blue`/etc. primitive slots),
  accent sky-blue, semantic success `#36C98F`/warning `#E7B94A`/danger
  `#F06A6A`/info `#62A8FF`.
- **New material tokens**: `--surface-mica` / `--surface-mica-border` /
  `--surface-mica-shadow` (sidebar, header, persistent panels — semi-opaque,
  low blur, fine border); `--surface-acrylic` / `--surface-acrylic-blur` /
  `--surface-acrylic-border` / `--surface-acrylic-shadow` (dialogs, drawers,
  command palette, popovers, dropdowns **only** — never a full-page surface,
  per the doc's own perf/mud warnings); `--surface-atmosphere` (the two
  subtle radial-gradient layers over the base dark background).
- **New scales**: elevation 0–4, radius 4/6/8/10/12/16/20/999px, type scale
  (Display 32/40/600 → Caption 12/16/400, Data 13/18/500, Large KPI
  28/34/600) — spacing's existing 4px-grid tokens are already compatible,
  verified against the doc's 4/8/12/16/20/24/32/40/48/64 scale.
- **Noise texture**: one shared SVG `feTurbulence` data-URI applied via a
  single `.surface-noise` utility class at 2–4% opacity — generated once,
  reused everywhere it's needed, not a `backdrop-filter` per element (the
  doc's own performance rule, §40).
- **`ThemeService`**: default `ThemePreference` resolution flips to `dark`
  for a first-run/no-`localStorage`-entry session; `light` and
  `high-contrast` remain full switcher options, restyled to the new
  radius/spacing/type scale while keeping high-contrast's "zero elevation,
  hard borders" WCAG rule untouched.
- **`primeng-preset.ts`**: rebuild the `definePreset(Aura, {...})`
  primitive/semantic/component blocks against the new token values — same
  mechanism, new numbers.
- **Gate:** `node scripts/generate-tokens.mjs` regenerates clean; every
  existing page still renders (no dangling `var()` references); **WCAG 2.2
  AA contrast check on every new text/surface pairing** — the doc's exact
  hex values get verified against real LPG surfaces, not assumed compliant,
  and nudged if any pairing fails; `nx build dashboard`.
- **Commit:** `feat(design-tokens): Fluent Glass palette — Mica/Acrylic materials, dark-first default`

### ✅ DONE 2026-09-05

- **Discrepancy found & corrected:** `tokens.css` / `tokens.ts` carried a
  "GENERATED FILE — regenerate via `node scripts/generate-tokens.mjs`"
  header, but **neither `tokens.json` nor that script exists anywhere in the
  repo** — the pipeline was never built; both files have always been
  hand-edited. Headers rewritten to say so. No generator was built (out of
  scope); editing is direct.
- **`tokens.css`** — new primitive scales (`--primitive-color-neutral-0..950`,
  `--primitive-color-primary-400..700`, `--primitive-color-accent-400/500`);
  the existing blue/gray/gas-blue/flame-orange primitives are kept (still
  used by the light theme + the brand-mark SVG). New material tokens
  (`--surface-mica*`, `--surface-acrylic*`, `--surface-atmosphere`,
  `--surface-noise-image` — a shared `feTurbulence` SVG data-URI). Additive
  radius (`--radius-xs/input/card/dialog/surface`) and type
  (`--typography-card-title/secondary/data/kpi-*`) scale steps — existing
  `--radius-sm/md/lg/full` and heading/body tokens left untouched so nothing
  currently rendering shifts. `--elevation-4` added.
- **Dark theme fully rebuilt** (`[data-theme='dark']` + the
  `prefers-color-scheme: dark` system-fallback block, kept in sync) on the
  Fluent Glass palette. **Every pairing WCAG 2.2 AA-verified by computed
  contrast ratio before selection** (documented inline): text-primary
  15.24:1, text-secondary 5.44:1, action-primary-as-text 4.54:1, status
  colours 6.3–10.3:1. Two deliberate exceptions, both documented in the
  file: disabled text (exempt from AA), and the filled-button background —
  which uses a **dedicated darker token** (`--component-button-primary-
  background`, primary-700, white-label contrast 5.55:1) rather than
  `--color-action-primary` (4.18:1 under white text). `primeng-preset.ts`
  gains a small `components.button.root.primary` override wiring that token,
  decoupled from `semantic.primary` (still used everywhere else).
- **Light + high-contrast**: deliberately light-touch — light keeps its
  existing values (dark is the primary experience; a full light redesign is
  out of this stage's scope), gets conservative translucent-white material
  fallbacks + `--elevation-4`. High-contrast gets opaque/no-blur material
  fallbacks + `--elevation-4: none`, keeping its zero-elevation WCAG rule.
- **`ThemeService`** — a session with no stored preference now defaults to
  `'dark'` (was `'system'`). "System" stays a first-class switcher option.
  Two specs updated.
- **`app.ts`** — injects `ThemeService` at bootstrap so `data-theme` is
  stamped on `<html>` before the first route paints, including `/login` and
  the other pre-shell screens (which don't otherwise touch it). Without this
  the theme only applied once the shell mounted post-login.
- **`styles.css`** — a "Materials" section with `.surface-mica`,
  `.surface-acrylic`, `.surface-noise` utility classes (unused until later
  stages opt surfaces in).
- **Deviation from the plan:** `primeng-preset.ts` needed almost no change —
  it's entirely `var(--token-name)`-driven, so the new dark values flow
  through automatically. The only edit was the button-contrast decoupling
  above (which the plan's own Stage 0 gate — "nudged if any pairing fails" —
  called for).
- **Gate:** `nx test shared-design-tokens` 5/5, `nx test shared-ui` 19/19,
  `nx test dashboard` 8/8, `nx lint` all three clean (3 pre-existing
  warnings in `shell-layout.ts`/`platform-shell.ts`, untouched), `nx build
  dashboard` production build clean, no budget warnings. Live dev-server
  check: dark theme applies at bootstrap on `/login`, every new token
  resolves, light/high-contrast switch still works, no console errors.
- **Note for Stage 1:** killed a 3-day-stale `nx serve dashboard` on :4200
  and started a fresh one (task `bvditb9xw`) — it's on current code.

## Stage 1 — Motion foundation: route transitions

- `provideRouter(appRoutes, withComponentInputBinding(), withViewTransitions({ onViewTransitionCreated }))`
  in `app.config.ts`; `onViewTransitionCreated` calls `skipTransition()`
  under `prefers-reduced-motion`.
- Retarget `--motion-duration-*`/`--motion-easing-*` to the doc's scale
  (Micro 100–140ms, Fast 160–200ms, Normal 220–280ms, Complex 300–400ms max;
  ease-out entering / ease-in exiting; `cubic-bezier(.2,.8,.2,1)` for
  page-level transitions).
- Page-enter treatment per doc §25: opacity 0→1, `translateY(6px)→0`,
  subtle blur-reduction, 180–240ms — styled on
  `::view-transition-old/new(root)`.
- Motion utility classes for Stage 3/8 entrance polish (`.animate-fade-up`,
  `.animate-stagger`).
- **Gate:** manual nav check (Chrome/Edge transition visible, Firefox
  graceful hard-cut fallback, reduced-motion toggle = no transition);
  `nx build dashboard`.
- **Commit:** `feat(dashboard): route-level view transitions + retuned motion tokens`

### ✅ DONE 2026-09-05

- **`app.config.ts`** — `provideRouter(appRoutes, withComponentInputBinding(),
  withViewTransitions({ skipInitialTransition: true, onViewTransitionCreated }))`.
  The hook calls `transition.skipTransition()` when
  `matchMedia('(prefers-reduced-motion: reduce)').matches` (with a
  `typeof matchMedia` guard). Comment on `provideAnimationsAsync()` updated to
  note routes don't use it.
- **`tokens.css`** — motion durations retuned to the doc §39 scale (micro
  100→120, small 150→180, medium 250→260, large 350→360; names unchanged,
  many consumers). Two new easings: `--motion-easing-accelerate`
  (`cubic-bezier(0.4,0,1,1)`, ease-in / exiting) and
  `--motion-easing-emphasized` (`cubic-bezier(0.2,0.8,0.2,1)`, the doc's
  page-transition curve). `tokens.ts` gains the two entries.
- **`styles.css`** — a "MOTION" section: `@keyframes lpg-route-out/in` +
  `::view-transition-old(root)` (fade out, `accelerate`, 180ms) /
  `::view-transition-new(root)` (fade + `translateY(6px)` settle,
  `emphasized`, 260ms). No blur in the keyframes — doc §40 warns off animated
  full-viewport blur and the plan keeps that restraint (deviation from §25's
  literal recipe, noted). Entrance utilities `.animate-fade-up` (with
  `--lpg-stagger-index` support) + `.animate-fade-in` for Stage 3/8. A
  `@media (prefers-reduced-motion: reduce)` block zeroes all four.
- **Gate:** `nx build dashboard` clean; `nx test` shared-design-tokens 5/5,
  dashboard 8/8, shared-ui 19/19; `nx lint` clean. Live dev-server check:
  `document.startViewTransition` **is invoked by the router on every
  navigation** (`vtCount` increments per nav), the `::view-transition-new(root)`
  CSS rule is present, new motion token values resolve.
- **Known dev-only console noise:** an interrupted navigation (a guard/redirect
  firing mid-transition, or `skipTransition()` under reduced-motion) makes
  Angular's own router log `AbortError: Transition was skipped` via
  `console.error` — but **only under `ngDevMode`**; it's silent in production
  builds (`_router-chunk.mjs` guards every `transition.*.catch` with
  `ngDevMode`). Not a regression, not fixable from app code.

## Stage 2 — App shell: Mica surfaces + nav polish

- `AppShellComponent`'s sidebar/header restyled onto `--surface-mica*`
  tokens (semi-opaque, low blur, fine border, subtle elevation) in place of
  today's solid surface tokens.
- Active nav item → low-opacity blue-tinted surface (token-driven), **no
  glow** (glow is reserved for hover/focus/live-indicator per the doc's
  restraint rule, §35).
- Icon-size convention applied consistently: 18px nav, 16px button, 20–24px
  feature icons.
- Brand flame mark kept as-is, now sitting on the Mica sidebar.
- **Gate:** `nx test shared-ui`; visual check in dark (primary) + light +
  high-contrast.
- **Commit:** `feat(shell): Mica sidebar/header + icon-sizing convention`

### ✅ DONE 2026-09-05

- **`app-shell.component.ts`** — `.shell__sidebar-wrapper` + `.shell__header`
  + `.shell__breadcrumb-wrapper` restyled onto `--surface-mica*`
  (semi-opaque tint, `--surface-mica-border`, `--surface-mica-shadow`; no
  blur — Mica isn't a blur material). `.shell__content` gets `position:
  relative` + `background: var(--surface-atmosphere)` (the Material-A base,
  doc §2) and the global `surface-noise` class; `.shell__main` →
  `background: transparent` so the atmosphere shows through. Active nav item:
  weight 700 → 600 (doc §13 restraint), keeps the themed
  `--color-highlight-*` pair. `.shell__collapse-toggle` → `--color-surface-
  overlay` + `--elevation-1` so it reads as a control over the Mica edge.
  `.shell__brand-mark` → `--primitive-color-flame-orange-500` (keeps its
  flame identity regardless of palette — was inheriting the now-blue
  `--color-action-primary`). Nav icon size → `--icon-size-md` token.
  Drive-by fix: a stale `var(--color-focus-ring)` (never existed) →
  `var(--color-border-focus)` on the breadcrumb focus ring.
- **`tokens.css`** — `--icon-size-sm/md/lg/xl` (16/18/20/24, doc §12);
  `--surface-noise-opacity` (0 in light/HC — nothing to break up there;
  0.03 in dark); `--surface-noise-image: none` in the HC block. `tokens.ts`
  gains the entries. **`styles.css`** — `.icon-sm/md/lg/xl` utilities;
  `.surface-noise::after` opacity now reads `var(--surface-noise-opacity)`.
- **Deviation:** first pass shifted active-nav text to
  `--color-text-primary` + the icon to `--color-action-primary` for a
  dark-mode blue accent — but light's `--color-highlight-background` is
  still a solid navy (light theme deliberately untouched this phase), so
  dark text on navy was **unreadable in light mode**. Caught in the
  light/HC visual check, reverted to the theme-safe `--color-highlight-
  color`. The dark blue-accent nicety is deferred (needs light's highlight
  token to become tint-based first — Stage 5 or a later polish).
- **Gate:** `nx build dashboard` clean; `nx test` shared-ui 19/19,
  shared-design-tokens 5/5; `nx lint` clean. **Visual check, logged in
  (real backend), all three themes:** dark — Mica sidebar/header distinct
  from the atmospheric content, flame brand mark, subtle blue-tint active
  nav, noise at 0.03; light — preserved (white Mica, navy active nav +
  white text); high-contrast — opaque surfaces, hard borders, no
  shadow/atmosphere/noise, blue active-nav text. Computed-style spot checks
  confirm every token resolves.

## Stage 3 — Shared UI primitives (`libs/shared/ui`)

Each `OnPush`, standalone, `lpg-` prefixed, Storybook story + unit test:

- **`StatCardComponent`** (`lpg-stat-card`) — doc §15: metric + comparison
  delta + mini trend sparkline + contextual icon; hover = elevation++/
  border-highlight/1–2px lift (never a jump).
- **`ActivityCardComponent`** (`lpg-activity-list`) — doc §17: time/icon/
  description/status rows, for "Recent Activity"-style panels.
- **`LiveIndicatorComponent`** (`lpg-live-indicator`) — a small, gently
  pulsing dot; used sparingly (live-route/active-delivery counts), never a
  whole-card animation.
- **`PageHeaderComponent`**, **`EmptyStateComponent`** (+ an error-state
  variant per doc §37: what happened / why / what to do / Retry),
  **`SkeletonBlockComponent`/`SkeletonListComponent`/`SkeletonTableComponent`**
  (shimmer via a token-duration-driven `@keyframes` sweep,
  reduced-motion-safe) — as previously scoped; `SkeletonTableComponent`
  wires into `DataGridComponent`'s currently-dead `loading` input.
- **`SectionCardComponent`** (`lpg-section-card`) — formalizes chart/list
  panel chrome.
- **Gate:** `nx test shared-ui`; `nx build dashboard` bundle-budget check
  (none of these should pull a heavy transitive dep, unlike AG Grid).
- **Commit:** `feat(shared-ui): StatCard/ActivityCard/LiveIndicator/PageHeader/EmptyState/Skeleton primitives`

### ✅ DONE 2026-09-05

- 7 components in `libs/shared/ui/src/lib/`, all `OnPush` / standalone /
  `lpg-` prefixed, each with a `.spec.ts` + `.stories.ts`, exported from the
  main barrel:
  - **`SkeletonComponent`** (`lpg-skeleton`) — **one parametric component**
    (`variant: block | text | circle | table` + `lines`/`rows`/`columns`)
    rather than the three the plan sketched; the shimmer keyframe is
    component-scoped (works in a story without the app's global CSS),
    reduced-motion-safe. Wired into `DataGridComponent`: `@if (loading())`
    now renders `<lpg-skeleton variant="table">` (that input was dead
    before).
  - **`EmptyStateComponent`** (`lpg-empty-state`) — icon/title/description +
    `[actions]` slot; `tone="error"` (doc §37) = same layout, danger icon,
    consumer supplies the Retry button + copy.
  - **`PageHeaderComponent`** (`lpg-page-header`) — title / subtitle /
    optional back-link / `[actions]` slot. Sits in the shell's title
    portal; renders the full header (incl. actions) when used standalone.
  - **`SectionCardComponent`** (`lpg-section-card`) — the standard panel
    surface (`--component-card-*`, `--radius-card`, `--elevation-1`) with an
    optional heading + `[headerActions]` slot.
  - **`StatCardComponent`** (`lpg-stat-card`) — doc §15 KPI card: label /
    value / contextual icon (6 tones) / delta with auto up/down/flat
    direction from a leading sign / caption / **inline-SVG sparkline** (no
    chart lib — a normalized polyline) / `loading` → skeleton. Restrained
    hover: 1px lift + border highlight + elevation bump.
  - **`LiveIndicatorComponent`** (`lpg-live-indicator`) — a small pulsing
    dot (a ring animates, never a card), `active`/`label`, reduced-motion
    static fallback.
  - **`ActivityListComponent`** (`lpg-activity-list`) — doc §17 time / icon /
    title / description / toned status-chip rows.
- **Deviations:** (a) 1 parametric `SkeletonComponent` vs 3; (b) each
  component self-contains its small entrance/shimmer keyframes rather than
  depending on Stage 1's app-global `.animate-*` utilities — so they render
  correctly in Storybook too.
- **Gate:** `nx test shared-ui` **41/41** (was 19; +22); `nx lint shared-ui`
  clean (2 pre-existing `any` warnings in `data-grid`, untouched);
  `nx build dashboard` clean, initial bundle **676.65 kB** raw / 148.72 kB
  transfer — under the 700 kB warn budget; the new primitives are
  tree-shaken out of every chunk until Stage 8 wires them into pages.
  **Visual check:** temporarily rendered all 7 on `home` in dark and
  screenshotted — stat cards (deltas, sparklines), skeleton table shimmer,
  section card, live indicator, activity list with status chips, empty
  state all render cleanly and on-theme; reverted the temporary wiring.
- **Pre-existing, not addressed:** `nx build-storybook shared-ui` was
  already broken before this stage (webpack can't parse the CSS `@import`s
  in `.storybook/preview.ts` — confirmed by stashing all Stage 3 changes and
  reproducing). The stories themselves are TS-valid and lint-clean; the
  Storybook build-pipeline fix is out of scope here.

## Stage 4 — Enterprise form + input + button system

- `FormFieldComponent` (`lpg-form-field`) + PrimeNG `p-floatlabel` (variant
  `on`) as the standard field wrapper — doc §19 spec: 40–44px input height,
  dark translucent surface, blue focus border + ring, 13px medium label,
  12px supporting text, semantic-red error **plus a non-color (icon)
  indicator** — never color-only.
- Pilot migration: Create-Order drawer, inventory operation forms, employee
  create/edit forms (same 3 as the earlier draft — deliberately not every
  form in one phase).
- Bundled hygiene fixes on the same files: `CustomerAutocomplete` → real
  `ControlValueAccessor` (removes the `[ngModel]`+`standalone` workaround
  inside the reactive form); `customer-onboarding-wizard.component.ts`'s
  `.toPromise()` → `firstValueFrom(...)`.
- Button system (doc §20): confirm/extend PrimeNG severities → Primary
  (filled blue) / Secondary (neutral elevated) / Tertiary (transparent) /
  Outline / Danger / Ghost, each with documented default/hover/pressed/
  focused/disabled/loading states via the preset — no new wrapper
  component, `p-button` stays.
- **Gate:** `nx test order-feature-orders inventory-feature-inventory tenant-admin-feature-employees`;
  keyboard-nav + validation-error check on all 3 pilot forms.
- **Commit:** `feat(forms): lpg-form-field + floating labels + button-state conventions; CVA + toPromise cleanup`

### ✅ Stage 4 (core) DONE 2026-09-05

- **`FormFieldComponent`** (`lpg-form-field`, `libs/shared/ui`) — `<p-floatlabel
  variant="on">` + projected control + required asterisk (auto-inferred from
  the control's `Validators.required`) + hint / error. Error shows on
  `invalid && (touched || dirty)`, carries an **icon as well as colour**
  (doc §28 — never colour-only), and maps validator keys → copy via
  `[messages]` with generic fallbacks. Reactivity: `AbstractControl`'s
  validity flags aren't signals, so a `toSignal(toObservable(control) →
  switchMap(c.events))` "tick" drives the computeds (re-subscribes if the
  `[control]` input is swapped). Spec (5) + story.
- **Employees form migrated** (`libs/tenant-admin/feature-employees`) — both
  the register and edit drawers (6 fields each) go from `.form-group` markup
  with **zero validation UX** to `lpg-form-field` + floating labels + inline
  errors; `email` gained `Validators.email`. Verified logged-in: floating
  labels + asterisks render, blur surfaces "First name is required." with the
  icon + red border, typing a valid value clears it, tab order is logical.
- **`.toPromise()` → `firstValueFrom`** in `customer-onboarding-wizard.
  component.ts`'s `submitWizard()` (3 calls) — the last `.toPromise()` in the
  repo.
- **Button + input conventions** (`styles.css`, doc §19/§20/§26) — `p-button`
  gains a subtle `scale(0.98)` press feedback (reduced-motion-guarded);
  inputs/selects → `--radius-input` (6px) + ~40px height; a comment documents
  the severity → Primary/Secondary/Tertiary/Outline/Danger/Ghost mapping.
- **Gate:** `nx build dashboard` clean; `nx test` shared-ui **45/45** (+4),
  tenant-admin-feature-employees + customer-feature-customers smoke pass;
  `nx lint` clean (2 pre-existing `any` in data-grid, 1 pre-existing
  `_error` in the wizard — all untouched).

### Stage 4b — remaining pilot form migrations (pending)

- **order-queue Create-Order drawer** (`libs/order/feature-orders`) — migrate
  to `lpg-form-field`; **and** move the customer from the out-of-form
  `selectedCustomer()` signal onto a real `customer` `formControlName`
  (`CustomerAutocomplete` is *already* a valid `ControlValueAccessor` — the
  audit's "mixed binding" is order-queue's form model, not the component;
  the `@if (selectedCustomer(); as c)` conditional sections need reworking to
  read the control). Higher risk (FormArray + conditional sections) — its own
  pass.
- **inventory operation forms** (`libs/inventory/feature-inventory`) — 5
  parallel `fb.group()` blocks → `lpg-form-field`.
- Split out from Stage 4 to keep that commit reviewable; the pattern is
  proven by the employees migration.

## Stage 5 — Data surfaces: tables, dialogs, drawers, toasts

- Migrate the 4 `libs/reporting/feature-reports` `p-table` views to
  `lpg-data-grid` (closes the two-table-system inconsistency); restyle
  `DataGridComponent`/AG Grid theme to doc §18: 48–52px rows, sticky header,
  subtle row-hover, semantic status badges, low-opacity blue selected-row
  tint.
- Dialogs → Acrylic material (doc §21): blur+saturate backdrop, `opacity
  0→1` + `scale(.97→1)` + `translateY(4px→0)`, 180–240ms, smoke-like (not
  full-app) backdrop.
- Drawers → doc §22: 400–520px, `translateX(24px)→0` + opacity, Acrylic
  surface.
- Toasts → doc §23: bottom-right, icon/title/message/optional-action/close,
  `translateY(8px)+opacity→translateY(0)+opacity 1`, 180–220ms.
- All retuning happens through the PrimeNG preset + the new material
  tokens — PrimeNG's overlay components already animate; this stage
  retargets material + timing, doesn't reinvent the mechanism.
- **Gate:** `nx test reporting-feature-reports`; visual check each report
  page retains its data and gains sort/filter/pagination; dialog/drawer/
  toast entrance timing check.
- **Commit:** `refactor(dashboard): Acrylic dialogs/drawers/toasts; reporting onto lpg-data-grid`

### ✅ DONE 2026-09-05

- **Reporting → `lpg-data-grid`** — all 4 views (`daily-sales`,
  `driver-performance`, `customer-consumption`, `gst-filing`) dropped
  `p-table` for `lpg-data-grid`; they gain sort / filter / pagination and now
  match the 9 operational grids. New `DataGridComponent` `autoHeight` input
  (`domLayout: 'autoHeight'` + a host class) so a report grid grows to its
  rows inside the padded panel instead of needing a fixed height. Currency /
  date / percent / decimal formatting moved into `@lpg/shared/ui`'s new
  `format.ts` (`Intl`, no locale registration) used as column
  `valueFormatter`s. The `@if (store.error())` blocks now render
  `<lpg-empty-state tone="error">`; the bare "Loading report…" text is gone
  (the grid's `[loading]` skeleton covers it).
- **Data-grid rows** `--component-data-grid-row-height` / `-header-height`
  40/44 → **48px** (doc §18).
- **Acrylic overlays** (`styles.css` + preset): `.p-dialog`, `.p-drawer`,
  `.p-toast-message` → `--surface-acrylic*` (translucent + `blur(20px)
  saturate(120%)` + fine border + strong shadow). `.p-dialog-mask` /
  `.p-drawer-mask` get a 2px "smoke" blur; the scrim colour is now a
  **dark** `color-mix(neutral-0, transparent 45%)` in the preset's
  `semantic.mask` (Aura's `{text.color}`-based default produced a *light*
  scrim on the dark theme). `overlay.modal` radius → `--radius-dialog`
  (16px). Verified logged-in: drawer bg `rgba(28,38,52,0.62)` + the blur,
  mask a 55%-black 2px-blur scrim, no console errors; the reporting grids
  render formatted data with 48px rows + a pager.
- **Deviations:** (a) the drawer's *slide-in* stays PrimeNG's own animation
  (a full-width slide, not the doc §22 `translateX(24px)`) — retuning
  PrimeNG's animation trigger isn't worth it; the material + timing are
  applied. (b) Drawers use the same `--surface-acrylic` (62% opacity) as
  dialogs — readable, but if Stage 10 QA finds the blurred-content bleed
  behind a large empty form area distracting, bump a drawer-specific
  opacity. (c) `nx build-storybook` still pre-existingly broken (Stage 3
  note) — untouched.
- **Gate:** `nx build dashboard` clean; `nx test` reporting-feature-reports
  smoke, shared-ui 45/45, shared-design-tokens 5/5; `nx lint` clean (2
  pre-existing `any` in data-grid).

## Stage 6 — Command palette (Ctrl/Cmd+K)

- New shared component (`libs/shared/ui` or a new
  `libs/shared/command-palette`): global `Ctrl/Cmd+K` listener, Acrylic
  surface, large radius, keyboard-shortcut hints, `Esc` closes, focus
  returns to the trigger element (a11y requirement, doc §28).
- Search scope, deliberately bounded: static page/nav registry (reuses
  `ShellLayout.navGroups`'s existing structure — no duplicated nav list) +
  live customer search via the existing
  `CustomerService.list(skip, limit, search)` (already backs
  `CustomerAutocomplete`) + 2 quick-create actions (New Order, New
  Customer) reusing existing navigation patterns (`home.ts`'s
  `onNewBooking()`-style route+query-param trigger).
- Order search-by-number is **not** included in this stage (no existing
  typeahead endpoint) — noted as a follow-on if wanted.
- **Gate:** unit test for keyboard nav + fuzzy filter + focus-return;
  manual check for shortcut conflicts with the browser/OS and any existing
  app shortcuts.
- **Commit:** `feat(dashboard): global command palette (Ctrl/Cmd+K)`

### ✅ DONE 2026-09-05

- **`apps/dashboard/src/app/command-palette/`** (kept in the app, not
  `libs/shared/ui` — one consumer, needs app routes + `CustomerService`):
  - `CommandPaletteService` (`providedIn: 'root'`) — `isOpen` signal,
    `open()` captures `document.activeElement`, `close()` restores focus to
    it (doc §28). Self-registers `Ctrl/Cmd+K` via `KeyboardShortcutsService`.
  - `CommandPaletteComponent` (`lpg-command-palette`) — Acrylic panel
    (`--surface-acrylic*` + `--radius-dialog`), search input, grouped
    results (Navigation / Customers / Actions), a keyboard-hints footer.
    ArrowUp/Down move `activeId` (ARIA `aria-activedescendant` combobox
    pattern — options aren't tab stops), Enter runs, Esc / backdrop close.
    Subsequence `fuzzyScore` (exported, tested) ranks nav + actions;
    customer results come from a debounced (200ms, ≥2 chars, best-effort)
    `CustomerService.list(0, 6, q)`. Actions: "New order"
    (`/orders?create=true`) + "New customer" (`/customers/new`), reusing
    existing patterns. Reduced-motion-guarded entrance.
  - `shell-layout.ts` — `<lpg-command-palette [navItems]="flatNavItems()">`
    (`flatNavItems` = `navGroups().flatMap(g => g.items)`, reusing the
    permission-filtered nav, no duplication) + a header "Search · Ctrl K"
    trigger button next to the notification bell.
- **Deviations:** (a) tenant shell only — not `PlatformShell` (a
  super_admin session has no tenant, so customer search would fail and
  there are 3 nav items; low value). (b) `Ctrl/Cmd+K` won't fire while a
  text field is focused (inherited from `KeyboardShortcutsService`'s
  editable-target guard) — a header click still works. (c) order
  search-by-number not included (no typeahead endpoint), as planned.
- **Gate:** `nx test dashboard` **16/16** (+8: `fuzzyScore` ranking, service
  focus round-trip, component filter + ArrowDown + Enter + Esc); `nx lint
  dashboard` 0 errors (the listbox-option `<li>` carries a targeted
  eslint-disable with a rationale comment); `nx build dashboard` clean,
  initial bundle **678.5 kB** (+1.8 from the eager shell, under budget).
  **Verified logged-in:** Ctrl+K + trigger both open, input auto-focuses,
  "disp" → Dispatch, ArrowDown moves the row, live customer search returns
  real results, Esc closes and focus returns to the trigger; no console
  errors.

## Stage 7 — Design-system showcase page

- New route rendering the sections from the screenshot — Color System,
  Typography, Elevation/Radius, Materials (Mica/Acrylic/Noise), Form
  Components, Table, Chart Styles, Transitions & Animations, Design
  Principles — built entirely from Stage 0–6's real tokens/components (not
  hardcoded swatches), so it's both documentation and a living regression
  surface for future token edits.
- Access: available to any authenticated staff member (no sensitive data on
  the page) — reachable from a footer/settings link, not the primary nav.
- **Gate:** `nx test`; structural comparison against the reference
  screenshot.
- **Commit:** `feat(dashboard): design-system showcase page`

### ✅ DONE 2026-09-05

- **`apps/dashboard/src/app/design-system/design-system.page.ts`** — route
  `/design-system` (no permission gate — no tenant data; `app.spec.ts`'s
  "every route has a guard" invariant updated with a one-line exemption +
  rationale). 11 sections: **Color system** (semantic + surface swatches +
  the neutral 0–950 strip), **Typography** (9-step scale at real sizes),
  **Elevation** (0–4), **Radius** (8 steps), **Materials** (Mica / Acrylic /
  atmospheric-base + noise), **Buttons** (all 6 severities + loading /
  disabled / icon), **Form components** (`lpg-form-field` with a live error,
  select, date picker, toggle, checkbox), **Data grid**, **Data display**
  (`lpg-stat-card` with sparkline + loading, `lpg-activity-list`,
  `lpg-live-indicator`, `lpg-skeleton`, `lpg-empty-state`), **Transitions**
  (the motion token table), **Design principles** (6 cards). Every
  colour / size / duration value is **read live** from
  `getComputedStyle(documentElement)` via a `resolve()` computed, re-run on
  a `data-theme` / `style` MutationObserver — so it stays a truthful
  regression surface as tokens change.
- **`ProfileMenuComponent`** — a "Design system" (`pi pi-palette`) menu item
  linking `/design-system`, between Account Settings and the theme picker.
- **Deviations:** (a) no dedicated "Chart styles" section with mini line /
  area / bar previews (the reference has these) — the `lpg-stat-card`
  sparkline stands in for the charting aesthetic; `home`'s real charts cover
  the rest. (b) The profile-menu link hard-codes `/design-system` in the
  shared `ProfileMenuComponent` (already dashboard-shell-scoped infra per
  its own docstring) — a dead link if that component is ever reused without
  the route.
- **Gate:** `nx build dashboard` clean; `nx test dashboard` **16/16**,
  shared-ui **45/45**; `nx lint` clean (pre-existing warnings only).
  **Verified logged-in:** all 11 sections render, swatch values match the
  live tokens (`#3978e8` etc.), all button severities + form controls +
  the grid + the data-display components display correctly on the dark
  theme; the profile-menu link resolves.

## Stage 8 — Rollout to flagship pages

- Apply Stage 3's primitives to `home.ts` (Agency Overview — highest-
  traffic, worst offender for hand-rolled CSS) + 2–3 more pilot pages
  (order queue, customer list, inventory): `StatCardComponent` (with
  sparkline) replaces `.kpi-card`, `ActivityCardComponent`/
  `LiveIndicatorComponent` for the deliveries/recent-activity sections,
  `SectionCardComponent`/`EmptyStateComponent`/`PageHeaderComponent`
  elsewhere.
- Staggered fade-up entrance on `@for`-rendered KPI cards/rows via Stage
  1's utility classes.
- Scoped as "flagship + a few" — remaining pages get the primitives
  opportunistically or in a tracked follow-on.
- **Gate:** `nx test dashboard` + affected libs; `nx build dashboard`
  budget check; visual smoke in dark/light/high-contrast.
- **Commit:** `feat(dashboard): roll out Fluent Glass primitives to home + pilot pages`

### ✅ DONE 2026-09-05

- **`home.ts` rebuilt** (−148 net lines) on the Stage 3 primitives:
  `PageHeaderComponent` (title portal), **6 `StatCardComponent`s** in a grid
  with `.animate-fade-up` + `--lpg-stagger-index` per card, `SectionCardComponent`
  for the two chart panels + the inventory-by-status + pricing sections,
  `ActivityListComponent` for Recent Activity (was the full AG Grid), an
  `EmptyStateComponent` in each data-less branch, a `SkeletonComponent` while
  loading. ~180 lines of hand-rolled `.kpi-card` / `.panel` / `.inventory-card`
  / `.price-card` CSS deleted; `KpiData.colorClass` → `tone: StatTone`.
- **Page-header rollout** — `order-queue`, `feature-customers`,
  `feature-inventory`, `feature-employees` swap their
  `<div class="page-header__text"><h1>…` markup for `<lpg-page-header>`.
- **`StatCardComponent` polish** — the delta/caption foot row no longer
  renders when both are empty (home's KPIs have no time-series), so the
  cards aren't left with dead space.
- **Deviations:** (a) home's stat cards show label + value + icon only —
  the dashboard summary carries counts, not history, so no sparkline /
  delta (valid pattern). (b) Recent Activity is now the lighter
  `ActivityListComponent` (doc §17) rather than the detailed audit grid —
  the copy-id affordance moves to `/admin/audit-log`, which keeps the full
  grid. (c) `LiveIndicatorComponent` isn't placed on home (no live-delivery
  section to attach it to). (d) The other feature-list pages
  (drivers/vehicles/complaints/invoices/…) still use raw `.page-header`
  markup — opportunistic follow-on, the pattern is proven.
- **Gate:** `nx build dashboard` clean, initial bundle **678.9 kB** (under
  budget); `nx test` dashboard **16/16**, shared-ui **45/45**, the 4 touched
  feature libs smoke-pass; `nx lint` clean (0 new — the pre-existing
  `_error` / `_condition` / `any` warnings only). **Verified logged-in:**
  home renders 6 stat cards + 2 charts + activity list cleanly in **dark
  and light**; the customers page header renders through
  `lpg-page-header`; no home-specific console errors.

## Stage 9 — Hygiene & cleanup

- Drop unused `@angular/material` (keep `@angular/cdk` — used for
  `PortalModule`); refresh lockfile.
- Fix `lib-notification-drawer` → `lpg-notification-drawer` selector
  prefix.
- Confirm all phase-authored components are `OnPush` (pre-existing ~32%
  gap elsewhere stays an explicit out-of-scope follow-up).
- **Gate:** `nx run-many -t lint,test,build` across every touched project.
- **Commit:** `chore(frontend): drop unused Angular Material dep; fix notification-drawer selector prefix`

## Stage 10 — Verification + docs

- Run the doc's own **§44 Final Design Test** (10 questions — hierarchy in
  2s, keyboard-only operability, text-over-translucent-surface readability,
  motion communicates something, calm-for-long-sessions, cross-component
  consistency, obvious semantic states, business-health-at-a-glance, and
  "does it still work without gradients/blur/animation") as the phase's
  literal acceptance checklist.
- WCAG 2.2 AA re-verification pass specifically on the shipped dark theme
  (not just Stage 0's spot-checks).
- `planning/features/29-dashboard-enterprise-ux/STATUS.md`;
  `libs/shared/ui/README.md`; Storybook updates; memory update.

---

## Risks / notes

- **This is the largest phase of this kind to date (11 stages)** — a full
  visual identity change plus a new feature, not incremental polish. Expect
  this to span several sessions; commit-per-stage (ask before each, as
  always) keeps it bisectable.
- **Adopting the doc's exact palette (the user's choice) means losing the
  gas-blue/flame-orange brand identity from the systematic token set** —
  the flame mark logo itself is unaffected (it's iconography, not a token),
  but every other "branded" surface becomes the reference's enterprise
  blue. Worth a final look-over once Stage 0 lands, before Stage 8's
  rollout makes it pervasive.
- **Dark-as-default is a visible behavior change for every existing user**
  on their next login — worth a heads-up/changelog note, not just a silent
  flip.
- **Contrast verification on Stage 0 is non-negotiable, not optional** —
  the doc's own hex values are a design intent, not a guarantee; some
  neutral-on-neutral text pairings in a dark Mica scheme commonly need a
  nudge to clear AA, and this app already has a WCAG-conscious
  high-contrast mode that raises the bar.
- **Command palette scope creep risk** — bounded explicitly to nav +
  customer search + 2 create actions in Stage 6; order/invoice/etc. search
  is a named follow-on, not silently expanded scope.
- **Acrylic (`backdrop-filter`) stays on transient surfaces only**
  (dialogs/drawers/palette/popovers) per the doc's own performance section
  (§40) — never applied to the 9+ list pages' repeated cards, which use the
  cheaper Mica/solid surfaces instead.

## References

- Attached: `GAS Fluent Glass Enterprise Design System Prompt.md` (source
  spec) + reference screenshot
- `libs/shared/design-tokens/src/lib/tokens.json` / `tokens.css` /
  `generate-tokens.mjs` — the token pipeline this phase re-values rather
  than replaces
- `libs/shared/design-tokens/src/lib/primeng-preset.ts` — the Aura-based
  preset rebuilt in Stage 0
- ADR-020 / ADR-028 — AG Grid-behind-`lpg-data-grid` rule extended to
  reporting in Stage 5
- ADR-018 — 100%-lazy-loaded routing Stage 1's transitions sit on top of
- `apps/dashboard/project.json` — bundle budgets checked at every stage
  gate
