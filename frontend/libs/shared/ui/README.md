# shared-ui

Cross-feature presentational components, cell renderers and formatters for the
dashboard app. Every component is standalone, `OnPush`, and prefixed `lpg-`.
Import from the barrel:

```ts
import { StatCardComponent, EmptyStateComponent, formatCurrencyInr } from '@lpg/shared/ui';
```

The visual language (Fluent Glass — Mica/Acrylic surfaces, the enterprise-blue
palette, motion) lives in `@lpg/shared/design-tokens`; these components only
consume `var(--…)` tokens, never raw hex. See
`planning/features/29-dashboard-enterprise-ux/` for the design system rationale
and `/design-system` in the running app for a live showcase.

## Layout & page scaffolding

| Component | Selector | Key inputs | Notes |
|---|---|---|---|
| `PageHeaderComponent` | `lpg-page-header` | `title` (req), `subtitle`, `backLink`, `backLabel` | Drop into the shell title portal. `[actions]` content slot for right-aligned buttons. |
| `SectionCardComponent` | `lpg-section-card` | `heading`, `hasHeaderActions` | Mica card wrapper for a dashboard panel. `[headerActions]` + default slot. |
| `StatCardComponent` | `lpg-stat-card` | `label` (req), `value` (req), `icon`, `tone`, `delta`, `deltaDirection`, `caption`, `trend: number[]`, `loading` | KPI tile with an inline SVG sparkline. `tone: 'primary' \| 'info' \| 'success' \| 'warning' \| 'danger' \| 'neutral'`. 1px hover lift only. |

## State & feedback

| Component | Selector | Key inputs | Notes |
|---|---|---|---|
| `SkeletonComponent` | `lpg-skeleton` | `variant: 'block'\|'text'\|'circle'\|'table'`, `width`, `height`, `lines`, `rows`, `columns` | Reduced-motion-safe shimmer. `variant="table"` is wired into `lpg-data-grid`'s own loading state. |
| `EmptyStateComponent` | `lpg-empty-state` | `title` (req), `description`, `tone: 'neutral'\|'error'`, `icon` | `[actions]` slot. Use `tone="error"` for load failures. |
| `LiveIndicatorComponent` | `lpg-live-indicator` | `active`, `label`, `ariaLabel` | Pulsing dot; falls back to a static dot under `prefers-reduced-motion`. |
| `ActivityListComponent` | `lpg-activity-list` | `items: ActivityItem[]` (req) | Read-only "recent activity" list. `ActivityItem = { time, icon, title, description?, status?, statusTone? }`. |

## Forms

| Component | Selector | Key inputs | Notes |
|---|---|---|---|
| `FormFieldComponent` | `lpg-form-field` | `label` (req), `for`, `hint`, `control: AbstractControl`, `messages: Record<string,string>`, `required` | Wraps a projected control in `p-floatlabel variant="on"`, renders hint + validator-keyed error text. Pass the `FormControl` so it can react to `touched`/`dirty`/status via the control's `events` stream. |

Reactive-forms field pattern:

```html
<lpg-form-field label="Email" for="email" [control]="form.controls.email"
  [messages]="{ email: 'Enter a valid email address.' }">
  <input pInputText id="email" formControlName="email" />
</lpg-form-field>
```

## Data grid

`DataGridComponent` (`lpg-data-grid`) is the only sanctioned grid (ADR-020 /
ADR-028 — AG Grid stays behind this wrapper; feature libs never import AG Grid
types). Inputs: `rows` (req), `columns: DataGridColumn<TRow>[]` (req),
`ariaLabel` (req), `selectionMode`, `loading`, `pageSize` (default 25),
`autoHeight`. Use `autoHeight` for report tables that should grow with content
rather than scroll inside a fixed viewport.

Companion cell renderers / helpers, also from the barrel: `StatusChipCell`,
activity cells (`activity-cells`), `PreviewDialog`, `HasPermissionDirective`,
`toSentenceCase`.

## Formatters (`format`)

`Intl`-based, no locale registration:

- `formatCurrencyInr(value)` — ₹ with Indian digit grouping
- `formatReportDate(value)` — short date
- `formatPercent(value, digits = 2)`
- `formatDecimal(value, digits = 1)`

## `p-button` convention

Filled (primary) actions use PrimeNG's default styling — the preset already maps
it to the AA-safe `--component-button-primary-*` tokens. For secondary actions
use `[text]` or `severity="secondary"`; do not hand-roll button colours. The
dark theme's filled-button background is deliberately a step darker than
`--color-action-primary` so white label text clears WCAG AA (see
`design-tokens/src/lib/primeng-preset.ts`).

## App shell

`AppShellComponent`, `HeaderPortalDirective` / `HeaderTitlePortalDirective`
(via `@lpg/shared/ui/app-shell`), `BreadcrumbService`, `ProfileMenuComponent`,
`NavItem`.

## Storybook

Each component ships a `*.stories.ts`. `nx build-storybook shared-ui` is
currently broken upstream (a webpack CSS `@import` parse issue, unrelated to
these files); the story files are TS-valid and lint-clean and render under
`nx storybook shared-ui` in dev.

## Running unit tests

`nx test shared-ui`
