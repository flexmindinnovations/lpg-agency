# Tasks — 65 dashboard revamp

## Phase 1 (this change)
- [x] T-01 Add `echarts` 6.1; `@lpg/shared/ui/charts` entry point (alias in `tsconfig.base.json`)
- [x] T-02 `ChartComponent` wrapper: SVG renderer, tree-shaken modules, resize, theme tokens, reduced motion, dispose
- [x] T-03 `ChartCardComponent`: heading, subtitle, skeleton at final height, empty state, "View as table", text alternative
- [x] T-04 Pure option mappers + unit tests (pipeline, drivers, cash, revenue, stock, reorder, TDT, refills)
- [x] T-05 Home data store: per-widget load state, no skeleton flicker on refresh, websocket-driven refresh
- [x] T-06 Widgets W01–W10 and the new Home layout; remove master-data counts, doughnut, mini-cards, price cards
- [x] T-07 KPI strip with real deltas and animated sparklines (extend `StatCard`)
- [~] T-08 Verify in the browser: light, dark and a phone width done (sample data); high-contrast theme and reduced motion not checked in a browser, and not against a busy real agency
- [x] T-09 Lint, tests, build; bundle impact of the chart chunk recorded in STATUS.md

## Follow-ups (not in this change)
- [ ] T-10 Backend: `/dashboard/overview`, `/attention`, `/stock` (by cylinder type), `/receivables-aging`, `/demand-heatmap`, `/compliance-timeline`, `/complaints-sla` (report section 9), with RLS, Redis cache and tenant-isolation tests
- [ ] T-11 Deep-link filters on Orders, Complaints, Invoices, Dispatch so chart clicks land filtered
- [ ] T-12 Chart tokens in `tokens.json` (series, sequential, diverging, status) with a contrast test per theme
- [ ] T-13 Global date range, comparison and branch controls with URL state; saved views
- [ ] T-14 P2 widgets: receivables ageing, demand heatmap, failed-delivery reasons, compliance timeline, complaints vs SLA
- [ ] T-15 Migrate the licence page off PrimeNG `p-chart`, then drop `chart.js`
- [ ] T-16 Storybook stories and Playwright/axe checks per widget, per theme
- [ ] T-17 Owner decisions: targets, "today" definition, AMDC capture, phone priority, map tiles (report section 11.3)
