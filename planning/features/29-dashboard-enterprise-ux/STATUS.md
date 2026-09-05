# Status: Dashboard Fluent Glass Enterprise Overhaul

**Phase:** 29
**Status:** Stages 0–10 + 4b done 2026-09-05. The dashboard app now runs the
Fluent Glass design system: enterprise-blue palette, Mica/Acrylic materials,
dark-as-default, route + micro motion, a shared `lpg-` primitive set, a global
command palette, and a live design-system showcase.

## Context

The dashboard shipped functional but visually dated — a stale token file that
claimed a generator that doesn't exist, PrimeNG defaults barely themed, no
motion, `p-table` in reporting, ad-hoc page headers and empty states per
feature. The user chose a full visual identity change to the reference spec
(`GAS Fluent Glass Enterprise Design System Prompt.md`): the doc's **exact**
palette (not a reinterpretation of the gas-blue/flame brand), dark as the new
default, command palette in scope. Plan: [PLAN.md](./PLAN.md).

## What shipped

| Stage | Commit | Summary |
|---|---|---|
| 0 — Tokens & materials | `efa92b0` | `tokens.css` re-valued to the Fluent Glass palette (neutral 0–950, primary 400–700, accent, semantics); Mica/Acrylic/atmosphere/noise surface tokens; radius + icon-size + typography scales; dark becomes the default preference; honest "hand-maintained" header (no `tokens.json`/generator exists). `primeng-preset.ts` filled-button decoupled from `semantic.primary` for AA. |
| 1 — Motion foundation | `d59d115` | `withViewTransitions()` (skips initial + `prefers-reduced-motion`); `::view-transition-old/new(root)` fade/translate; `.animate-fade-up/-in` with staggerable delay; motion tokens retuned to 120/180/260/360 ms + named easings. |
| 2 — App shell | `0ff6781` | Sidebar / header / breadcrumb bar on Mica; content on the atmosphere gradient + noise; active-nav weight/tint retuned (theme-safe `--color-highlight-*`); nav icon sizing convention. |
| 3 — Shared primitives | `297479b` | `lpg-skeleton`, `lpg-empty-state`, `lpg-page-header`, `lpg-section-card`, `lpg-stat-card` (inline SVG sparkline), `lpg-live-indicator`, `lpg-activity-list` — each `OnPush` + spec + story. Skeleton wired into `lpg-data-grid` loading. |
| 4 — Form system | `094e0d9` | `lpg-form-field` (float-label `variant="on"` + validator-keyed errors, reacts via the control's `events` stream); employees register + edit forms migrated; `p-button` active-press feedback; `.toPromise()` → `firstValueFrom` in the onboarding wizard. |
| 4b — order + inventory forms | _this_ | order-queue Create-Order drawer + all six inventory operation drawers (25 fields) onto `lpg-form-field` + floating labels + inline errors; order-queue's customer moved onto a real `formControlName` bound to the `lpg-customer-autocomplete` CVA (the `[ngModel]` + `{ standalone: true }` workaround removed). |
| 5 — Data surfaces | `a05c1cc` | Dialogs / drawers / toasts onto Acrylic + backdrop blur; `--radius-dialog`; all four reporting tables `p-table` → `lpg-data-grid` (`autoHeight`, shared `format` helpers, `lpg-empty-state` error branch); data-grid row/header height to 48px. |
| 6 — Command palette | `d6b133a` | `Ctrl/Cmd+K` palette — nav (reuses the permission-filtered `navGroups`), debounced customer search, 2 quick-create actions. Acrylic panel, ARIA combobox, focus round-trip. Shell top-right trigger button. |
| 7 — Showcase page | `1e8e18d` | `/design-system` — 11 sections reading live `getComputedStyle` values, re-rendering on `data-theme` change. Profile-menu entry. |
| 8 — Rollout | `37d1ca5` | `home` rebuilt on the primitives (−148 net lines, all 6 KPIs on `lpg-stat-card` with `StatTone`, `lpg-activity-list`, `lpg-section-card`, empty/skeleton states); `lpg-page-header` on orders / customers / inventory / employees. |
| 9 — Hygiene | `bee83bc` | `@angular/material` dropped (zero usage; surgical lockfile diff; `@angular/cdk` kept); all 10 phase-authored components confirmed `OnPush`; `catch (_error)` warning cleared. `lib-notification-drawer` rename **skipped** — `lib-` is a config-enforced domain convention, not an accident. |
| 10 — Verification + docs | `dd521fb` | WCAG AA re-verification on the shipped dark theme (one failing pairing found + fixed, below); this doc; `libs/shared/ui/README.md`; §44 test. |

## Stage 10 — WCAG 2.2 AA re-verification (dark theme)

Live resolved token values were pulled from the running app and run through a
contrast audit **with alpha compositing** for the translucent Mica / Acrylic /
highlight surfaces (script kept in the session scratchpad).

**One failure found and fixed:**

- `--color-action-primary` was `#3978e8`. As *text / link / border* colour it
  measured **4.31:1 on the `#101720` card surface** and 4.24:1 for a selected
  dropdown option (primary label on the primary@12 % tint over the overlay
  surface) — both below the 4.5:1 AA threshold for normal text.
- **Fix:** `--color-action-primary` → `#4f8df7` (primitive `primary-500`),
  `--color-action-primary-hover` → `#6ea8ff` (`primary-400`, a brighter hover
  as is conventional for links). Now **5.0–5.9:1** as text across every dark
  surface; hover **7.5–7.9:1**. Applied in both the `[data-theme='dark']` block
  and the `@media (prefers-color-scheme: dark)` mirror.
- The filled primary button is **unaffected** — it keeps its own
  `--component-button-primary-background: #2864cc` (white label text 5.55:1),
  decoupled from `semantic.primary` back in Stage 0.
- `--component-avatar-background` moved `#3978e8` → `#2864cc` for the same
  reason (white initials, 5.55:1).
- PrimeNG `highlight.color` / `focusColor` changed from `--color-action-primary`
  to `--color-text-primary` — the selected-item label is now a neutral
  high-contrast colour (9–13:1 on the tint on every dark surface); the tint
  background + hover carry the "selected" affordance.
- `--color-highlight-background` re-tinted to the new primary rgb (0.22 alpha);
  white nav-active label on it is 13:1.

Light and high-contrast themes were not touched (verified live — their
`--color-action-primary` etc. resolve unchanged).

**All other dark-theme pairings pass:** body text 13–15:1, secondary text
4.7–5.4:1 (overlay is the floor at 4.67), disabled text exempt, all four
semantic colours ≥ 3:1 as large text / UI on raised, focus ring 5.9:1.
Known soft point, accepted: `--color-border-strong` vs base is ~1.5:1 — it is a
decorative container/hover border, not a state indicator (SC 1.4.11 n/a); the
identifying borders (inputs) use `--color-border-default` + a distinct focus
treatment.

## §44 Final Design Test

| # | Question | Verdict |
|---|---|---|
| 1 | Hierarchy obvious in 2s? | Yes — `lpg-page-header` title/subtitle, KPI row, then section cards; consistent on every flagship page. |
| 2 | Important info prioritised? | Yes — KPI value at `--typography-kpi` 28/600, semantic-toned icons, sparkline; secondary data at 13px muted. |
| 3 | Keyboard-only operable? | Yes — `Ctrl/Cmd+K` palette with full arrow/enter/esc + focus round-trip; every route has a guard or a documented exemption; PrimeNG focus states on the token focus ring. |
| 4 | Text readable over every translucent surface? | Yes — the Stage 10 audit composited every Mica/Acrylic/tint pairing; the one sub-AA case was fixed. |
| 5 | Motion communicates something? | Yes — route fade/translate signals navigation; `.animate-fade-up` stagger signals list arrival; 1px KPI hover lift signals interactivity. All `prefers-reduced-motion`-gated. |
| 6 | Calm for long sessions? | Yes — dark default, low-chroma neutrals, noise at 0.03 opacity, motion ≤ 360 ms, no autoplaying or looping animation (live-indicator pulse excepted and reduced-motion-safe). |
| 7 | Consistent across components? | Yes — one primitive set, all `lpg-` prefixed, all token-driven; `p-*` bound to the same tokens via the preset. |
| 8 | Semantic states obvious? | Yes — success/warning/danger/info tokens ≥ 3:1, used consistently by `lpg-stat-card`, `lpg-activity-list`, chips, toasts. |
| 9 | Business health at a glance? | Yes — home leads with 6 KPIs + fleet/inventory charts + recent activity above the fold. |
| 10 | Works without gradients/blur/animation? | Yes — high-contrast theme ships opaque material fallbacks (`--surface-acrylic-blur: none`, `--surface-atmosphere: none`, `--surface-noise-image: none`, `--elevation-4: none`); reduced-motion disables all transitions; layout is flexbox/grid, not effect-dependent. |

## Verification

- **Gate:** `nx build dashboard` clean (~679 kB, within budget). `nx test`:
  shared-design-tokens 5/5, shared-ui 45/45, dashboard 16/16, reporting /
  employees / customers / orders / inventory green (7 projects, exit 0).
  `nx lint` dashboard + design-tokens: 0 errors (3 pre-existing warnings in
  `shell-layout.ts` / `platform-shell.ts`, not phase files).
- **Live:** dark theme resolves the new token values in the running app (HMR
  confirmed); `/design-system` and `home` render correctly; light + HC token
  values verified unchanged.

## Deferred / follow-ups (not in scope)

- **Storybook build** — `nx build-storybook shared-ui` is broken upstream (a
  webpack CSS `@import` parse issue, pre-existing, unrelated to phase files).
  Story files are TS-valid and lint-clean; `nx storybook shared-ui` dev serves.
- **Command palette scope** — order / invoice / delivery search is a named
  follow-on, deliberately not in Stage 6.
- **`prefers-color-scheme` for brand-new users** — dark is now the stored
  default; worth a changelog line since it's a visible change on next login.
- The pre-existing ~32% non-`OnPush` component gap elsewhere in the app is
  untouched.

## Notes

- Plan: [PLAN.md](./PLAN.md)
- Source spec: `GAS Fluent Glass Enterprise Design System Prompt.md` (+ the
  reference screenshot the user supplied).
- Component docs: [`frontend/libs/shared/ui/README.md`](../../../frontend/libs/shared/ui/README.md).
