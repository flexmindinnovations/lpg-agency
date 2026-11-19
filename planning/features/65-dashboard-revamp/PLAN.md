# 65 — Dashboard revamp (Home page)

Goal: replace the Home page's master-data counts, 7-slice doughnut and plain lists with an answers-first dashboard of animated, interactive charts that an agency owner, manager, dispatcher or accountant acts on.

Source: [`docs/research/dashboard-revamp.md`](../../../docs/research/dashboard-revamp.md) (research report, 2026-11-19). Read it for the reasoning, the full widget catalogue (W01–W24) and the open business questions.

## Scope of this feature (phase 1 — frontend, existing data only)
Only widgets whose data **already exists** in an endpoint (verdict EXISTS in the report). No backend change.

| Widget | Chart | Data today |
|---|---|---|
| Needs attention (W01) | ranked list | `GET /dashboard/operations` |
| KPI strip (W02) | tile + delta + animated sparkline | `/reporting/sales`, `/reporting/drivers`, operations, summary, TDT projection |
| Order pipeline (W03) | horizontal bars | operations `open_by_status` |
| Drivers today (W04) | stacked horizontal bars | `/reporting/drivers` |
| Cash on the road (W05) | ranked bars | `/cash-handovers/cash-in-hand` |
| Revenue trend (W06) | area + dashed prior period | `/reporting/sales` |
| Stock by status (W07-lite) | horizontal bars | summary `inventory_by_status` (no type split yet) |
| Reorder proximity (W08) | bullet bars | `/inventory/reorder-signals` |
| Delivery-time rating (W09) | star + distribution + 85% marker | `/tdt-rating/live-projection` |
| Refills due (W10) | histogram | `/customers/refill-due` |

## Decisions
- **Library: Apache ECharts 6.1** (Apache-2.0), tree-shaken from `echarts/core` with the SVG renderer, behind our own wrapper in a new secondary entry point `@lpg/shared/ui/charts` (same pattern as `data-grid`, kept out of the main barrel). Widgets load with `@defer`, so ECharts stays off the initial bundle.
- Charts read colours from the existing design tokens at runtime and re-read them on theme change (one observer, disconnected on destroy). No hard-coded colours. Dedicated chart tokens are a follow-up (T-12).
- Animated by default (bars grow, lines draw, sparklines draw in); off under `prefers-reduced-motion`.
- Every chart has a text alternative and a "View as table" toggle (WCAG 2.2 AA). Colour is never the only channel.
- Refreshes swap data in place; skeletons only on first load. Reserved heights avoid layout shift.
- Widgets are gated by permission codes (existing `*lpgHasPermission`), not role names.

## Out of scope (recorded in TASKS.md)
Backend aggregation endpoints (stock by type, receivables ageing, demand heatmap, compliance timeline, attention queue ranking), global date/branch controls, saved views, maps, Sankey, AI insights (paused by the owner), deep-link filters on target pages.
