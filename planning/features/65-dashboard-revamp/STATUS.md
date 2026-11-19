# Status — 65 dashboard revamp

**Phase 1 built** (2026-11-19), on branch `feat/dashboard-revamp-charts`. Frontend only, on data that already exists. See PLAN.md and TASKS.md.

## What changed
- Home now shows: a ranked "Needs attention" list, six KPI tiles (real deltas against the same weekday last week, animated sparklines), and eight animated charts: order pipeline, drivers today, revenue vs the previous 30 days, cash on the road, cylinder stock, close-to-reorder bullets, delivery-time rating, refills due. Recent activity stays as a card.
- Removed from Home: customer/driver/vehicle/godown counts, fleet-status bar, 7-slice doughnut, inventory mini-cards, price cards (data still in their modules).
- New `@lpg/shared/ui/charts` entry point: `ChartComponent` (ECharts, SVG renderer, tree-shaken), `ChartCardComponent` (states, "View as table", link to the module), `ChartThemeService` (one shared theme signal from the design tokens; replaces the per-page MutationObserver that leaked).
- New `ReportingService` in data-access (sales, driver performance). `echarts` 6.1 added.
- Each widget loads and fails on its own; refreshes swap data in place (no skeleton flicker); heights are reserved.

## Follow-up (2026-11-19): layout pass
- Order on Home is now: setup checklist, charts, "Needs attention", KPI tiles. Chart cards show at once; each chart loads into its card with `@defer` (ECharts is still lazy).
- All chart cards are one height (280 px, `grid-auto-rows: 1fr`); KPI tiles are one height too.
- Card help text uses PrimeNG `pTooltip` (not native `title`) on the subtitle and the "View as table" button.
- The setup checklist shows only while at least one step is incomplete (decided from the steps, not the server's `complete` flag). Recent activity shows 4 entries.

## Follow-up: revisits (2026-11-19)
- `DashboardData` is now a session-long root service, not per-visit. Coming back to Home shows the cached figures at once; today's figures are refetched only when older than 30 s, the slower ones (stock, sales history, rating, refills) when older than 2 min, plus any widget that never loaded. The websocket refresh runs only while Home is open.
- The cache is cleared when another user, agency or branch signs in, and when the IST day changes (no figures leak between users).
- Charts keep a per-session record (`ChartEntranceRegistry`): the draw-in entrance plays once per chart; on a return visit the chart appears already drawn and only changed values animate. A refresh with identical numbers is skipped. KPI sparklines and the attention rows follow the same rule.
- Not cached yet: the setup checklist still asks `/admin/setup-progress` on each visit.

## Follow-up: drawers (2026-11-19)
- Drawers have no backdrop blur and use a near-solid tint (`--glass-drawer-tint`, 97%). Measured on the notification list and the invoice drawer: about 7.7 ms per scrolled frame without the blur against 12 ms with it, and the blur was barely visible on the old 72% tint. Dialogs and menus keep the blur (they do not scroll long content).
- Inside `.p-drawer` the three page-surface colours are remapped to faint translucent washes (`--surface-inset`, `--surface-inset-strong`), so cards, rows and callouts no longer paint opaque white slabs; high contrast maps them back to solid. PrimeNG form fields stay solid (checked on Raise Complaint).
## Verified
- Jest: 101 tests in the dashboard app (new: model maths, chart option builders including tooltip escaping and reduced motion) and 104 in `shared-ui` (new: chart card states and table toggle). Lint and production build pass for `dashboard`, `shared-ui`, `shared-data-access`.
- In the dev server with sample responses (production has almost no data today): all 8 charts draw in light and dark; table toggle shows the same numbers; 375 px wide has no horizontal scroll; one chart's bad payload no longer breaks the rest.
- **Bundle:** the chart chunk (`home-charts`) is 605 kB raw / about 173 kB transferred, lazy via `@defer`, under the 200 kB limit set in the research. The initial bundle moved 771.6 -> 780.6 kB (still the existing over-budget warning; cause of the +9 kB not yet isolated). Home no longer loads Chart.js (the licence page still does, T-15).

## Not verified / known gaps
- High-contrast theme and `prefers-reduced-motion` in a real browser; screen reader pass; real-agency data volumes.
- Chart click-through lands on the module page unfiltered (deep-link filters are T-11).
- Stock is by status across all locations; the by-cylinder-type split needs the new endpoint (T-10).
- Series colours come from existing tokens, not dedicated chart tokens (T-12); the cyan series colour is below 3:1 on a white surface and is only used with value labels.
- The 85% delivery-time threshold is not drawn: it is tenant-configurable and not exposed to the dashboard.
