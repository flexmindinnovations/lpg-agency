# Dashboard Revamp: research and recommendation

**Date:** 2026-11-19 | **Scope:** the Home page ("Agency Overview") of the Agency Web Dashboard | **Status:** research only, nothing implemented.

**Evidence tags.** `[R]` verified in this repo (file or endpoint cited). `[W]` verified on the web this session (URL in section 12). `[S]` seen only as a search-result summary, page not opened. `[U]` could not verify; treat as a hypothesis. Where I ran out of verification budget I say so rather than fill the gap.

---

## 1. Executive summary

**Recommendation.** Replace the Home page's "counts plus two small charts" layout with an answers-first dashboard in six zones: (1) a ranked **"Needs attention"** queue, (2) a **KPI strip** where every tile carries a delta against a comparison period and a sparkline, (3) **today's flow** (order pipeline, drivers, cash on the road), (4) **money** (revenue trend, receivables ageing), (5) **stock** (by cylinder type and status, with reorder proximity), (6) **demand and service** (refills due, demand heatmap, delivery-time star rating, compliance expiries). Views vary by permission set, not by role name.

**Library.** Apache ECharts 6.1 (Apache-2.0), imported tree-shaken from `echarts/core`, behind our own thin Angular wrapper in a new secondary entry point `@lpg/shared/ui/charts`, the same pattern as `@lpg/shared/ui/data-grid`. It is lazy-loaded with `@defer`, so it stays out of the initial bundle. **Fallback:** keep Chart.js (already installed, 4.5.1, used through PrimeNG `p-chart`) and add `chartjs-chart-matrix` for heatmaps, accepting weaker accessibility and no native Sankey or treemap. AG Charts Community is rejected because heatmap, gauge, treemap and Sankey are Enterprise-only.

**Top 5 changes**

1. **Stop showing master-data counts.** Customers, drivers, vehicles, godowns, the price cards and the fleet-status bar describe setup, not operations. Replace them with exceptions and trends [R `apps/dashboard/src/app/home/home.ts`].
2. **Give every KPI context.** `StatCardComponent` already supports `delta`, `caption` and a sparkline `trend`, but Home passes none of them [R `libs/shared/ui/src/lib/stat-card/stat-card.component.ts`, `home.ts`]. Add one small composed endpoint that returns value, comparison value and a 7 to 30 day series per KPI.
3. **Split stock by cylinder type.** Today the stock chart sums 14.2 kg, 19 kg and 5 kg cylinders and every location into one doughnut [R `DashboardSummaryResponse.inventory_by_status`]. An owner decides on "how many days of 14.2 kg do I have", not on "7 statuses".
4. **Surface the regulatory number that can fine the agency.** The live delivery-time (TDT) star rating projection already exists (`GET /api/v1/tdt-rating/live-projection`) but is not on Home. OMC rules fine a "Poor" quarter at 20% of average monthly distributor commission [W HPCL MDG 2022 cl. 4.2].
5. **Fix the load behaviour.** KPI tiles pop in after the fetch (list starts empty, so the skeleton path never shows), and every live websocket event flips all cards back to skeletons. Use fixed-height placeholders and per-widget refresh.

**Biggest risks:** the ECharts chunk is about 2x Chart.js in gzip (to be measured in a one-day spike, section 8); several valuable widgets need new aggregation endpoints; no business targets are captured anywhere, so "vs target" must start as "vs baseline".

---

## 2. What the dashboard shows today, and what is wrong with it

### 2.1 Inventory of the current page [R `home.ts`, `setup-checklist.ts`]

| Block | Source | Verdict |
|---|---|---|
| Setup checklist (9 steps) | `GET /admin/setup-progress`, `tenant:configure` only, self-hides when done | Fine as an onboarding banner. Should collapse to a one-line progress bar, never sit above operational content once the agency is live. It already saves its height in `localStorage` to avoid layout shift. |
| "Today's operations" (9 to 14 tiles) | `GET /dashboard/operations` | Right idea, wrong form: 14 equal-weight tiles, no deltas, no ranking. Best raw material for the new attention queue and KPI strip. |
| 7 count tiles (Customers, Drivers, Fleet Vehicles, Godowns, Filled Cylinders, Needing Attention, Refills Due) | `GET /dashboard/summary`, `GET /customers/refill-due` | Five of seven are master-data counts that change monthly. They do not drive a decision. |
| Fleet Status bar chart | `vehicles_by_status` | A bar chart of two to four numbers. A sentence ("4 available, 1 in maintenance") conveys the same. |
| Cylinder Inventory doughnut (7 slices) | `inventory_by_status` | Many-slice doughnut, all cylinder types and locations summed. Hard to read, hides the type split. |
| "Inventory by Status" mini-cards | same data | The same numbers a third time (KPI tile, doughnut, mini-cards). |
| Cylinder Prices | `price_cards` | Configuration, not monitoring. Belongs in Settings. |
| Refills Due This Week | `GET /customers/refill-due?within_days=7` | Useful and unique; shown as a plain list. Needs a time dimension (when are they due) and an overdue count. |
| Recent Activity | audit log, 8 items | Low value at the top level; keep as a collapsed footer widget. |

### 2.2 Technical and UX defects found in code

1. **Context-free KPIs.** `<lpg-stat-card>` is rendered without `delta`, `caption` or `trend` for every tile [R `home.ts` template]. A bare "Failed today: 3" cannot tell the user whether that is bad.
2. **Load shift (CLS) risk.** `kpis` is initialised to `[]` and only filled in `rebuildKpis()` after the first response, so the `@for` renders nothing at first paint and the `loading` skeleton inside `StatCard` is effectively unreachable on first load. The "Today's operations" section is gated by `@if (operationsKpis().length > 0)`, so it appears late and pushes everything down. Not measured here; Google's thresholds are 0.1 good and above 0.25 poor at the 75th percentile [W web.dev/articles/cls]. `SetupChecklist` already reserves height from `localStorage`, which shows the team hit this problem once.
3. **Skeleton flicker on live updates.** `loadDashboardData()` sets `loading` to true before every refetch and each `dashboard.metrics_stale` or `order.status_changed` websocket event (debounced 1 s) triggers it, so all tiles that exist flip to skeletons on every event.
4. **Four requests, all refetched together.** `getOperations`, `getSummary`, `listRefillDue` and `setup-progress`. The event handler re-requests the first two in full for any change, including events irrelevant to a given widget.
5. **Possible observer leak.** `effect(() => initCharts())` calls `updateChartTheme()`, which reads `this.summary()`. The effect therefore re-runs when the summary changes, and each run creates a new `MutationObserver` without disconnecting the previous one (`themeObserver` is overwritten). Only the last is disconnected in `ngOnDestroy`. Worth a test; I did not run it.
6. **Hard-coded colours and `any`.** `updateChartTheme()` falls back to literal hex values (`'#111827'`, `'#16a34a'`, `'#ff6f12'` and others) and four `eslint-disable no-explicit-any` types. AGENTS.md says never hardcode colours. The design docs promise a six-colour chart palette (`docs/ui/10-color-system.md` section 7, tokens `color-chart-series-1..6`), but **`design-tokens/tokens.json` contains no chart tokens** [R, grep for "chart" returns nothing in tokens.json].
7. **Chart.js is statically imported by PrimeNG.** `primeng/chart` has `import Chart from 'chart.js/auto'` at module top [R `node_modules/primeng/fesm2022/primeng-chart.mjs:4`]. In the existing build, the chunk containing Chart.js defaults is `chunk-ASQHT8e5.js`, 228,209 bytes raw / 77,616 bytes gzipped [R `frontend/dist/apps/dashboard/browser`, measured by gzip]. It is lazy (Home is a `loadComponent` route) but it is pulled in whole, all chart types registered.
8. **Latent count caps.** `invoice_snapshot` computes `on_hold_count` as `len(list_uninvoiced(limit=1000))`, capping the figure at 1000, and `low_stock_count` materialises the whole breached list to take its length [R `infrastructure/persistence/repositories/dashboard.py`]. Harmless at pilot scale; wrong at scale.
9. **No caching.** The design doc plans a 30 to 60 s Redis TTL for dashboard KPIs (`docs/data/15-reporting-data-model.md`), but neither dashboard endpoint touches Redis today [R grep of `application/dashboard`, `api/v1/routers/dashboard.py`, `dependencies/dashboard.py`].
10. **Mobile.** `docs/ui/06-dashboard-layout.md` says the dashboard is "not primary-optimized" under 768 px, yet the owner persona is described as smartphone-first and wanting "summarized views (KPI cards, charts)" (`docs/ui/02-user-personas.md`). The two documents disagree; see open question Q8.

### 2.3 Glass-style constraint (from `styles.css`)

The frosted glass is deliberately reserved for chrome: "Header, sidebar, dialogs, drawers and toasts only; never cards, rows or table cells" [R `styles.css` ~line 1374]. Dashboard widgets are cards, so they must stay on the solid `section-card` surface. Charts may use glass only for **popovers and tooltips** (which `.p-popover` and overlays already get). This overrides the brief's instruction to restyle widgets as glass panels; I recommend not doing so.

---

## 3. Questions each role asks, and the decision behind them

Roles in the system [R `fa52b77ec442_...rbac_tables.py`]: `super_admin`, `agency_admin` (the owner), `manager`, `warehouse_staff`, `dispatcher`, `accountant`, `driver`, `customer`. The Home endpoints are gated by `reports:read`, granted to all staff roles except `driver` and `customer` [R `b3f7c1d9e4a2_grant_reports_read_permission.py`]. Admins can also grant per-user permission overrides (`PUT /admin/users/{id}/permissions`), so **widgets must be gated by permission codes, not role names**, which is what `*lpgHasPermission` does today.

| Role | Question | Decision it supports | Metric family |
|---|---|---|---|
| Owner (`agency_admin`) | Is today on track vs a normal day? | Intervene, or leave it | Deliveries vs baseline, revenue vs last same weekday |
| Owner | Where is my money stuck? | Chase customers, stop supply to defaulters | Receivables ageing, cash with drivers, uninvoiced orders |
| Owner | Am I about to be fined or blocked? | Fix delivery times, renew licences | TDT live star rating, compliance expiries, empty-vs-filled mismatch |
| Owner | Who or what is underperforming? | Coaching, route changes | Driver delivered/failed, cash accuracy, branch comparison |
| Manager | What is waiting on me? | Approve or reject | Cancellations to approve, credit-note and refund approvals, reconciliation approvals, escalated complaints |
| Manager | Are complaints going out of SLA? | Reassign, escalate | Open complaints by age vs `sla_due_at`, by category |
| Dispatcher | Which orders are not yet on a trip, and how old are they? | Build trips now | Orders waiting by status and age |
| Dispatcher | Which stops are failing or late, where are my vans? | Reroute, call customer | Stops done/pending/failed per driver, failure reasons, live map |
| Warehouse staff | How many filled cylinders of each type can I load tomorrow? | Request stock, schedule GRN | Filled by type, reorder-point proximity, empties awaiting return to OMC |
| Warehouse staff | Do my books match the floor? | Raise a reconciliation | Reconciliation variances pending, damaged/leak/quarantine counts, test-due cylinders |
| Accountant | Which invoices are overdue and by how much? | Reminders, holds | Ageing buckets, top debtors, invoices on hold |
| Accountant | Is the day's cash accounted for? | Verify handovers | Collections by method, cash per driver, handovers to verify, shortfall/excess |
| Accountant | What is my GST position this period? | Filing prep | GST by filing period (low-frequency, keep out of the first screen) |

**Domain facts behind these questions** (the repo already encodes most of them):

- Order lifecycle `booked, confirmed, assigned, ready_for_dispatch, out_for_delivery, delivered, failed_delivery` [R `_OPEN_STATUSES` in `repositories/dashboard.py`]; five failed-delivery reason codes (`customer_unavailable, wrong_address, payment_refused, vehicle_issue, safety_issue`) and booking sources (`mobile_app, staff, phone, walk_in, whatsapp, api`) and payment methods (`cash, upi, card, online_gateway, credit`) [R `domain/order/order.py`].
- Cylinder statuses `filled, empty, damaged, leakage, quarantine, repair, scrap`; inventory transaction types `grn_receipt, omc_return, load, unload, delivery, collection, status_change, adjustment, reconciliation` [R `domain/inventory/inventory_location.py`]; OMC codes `iocl, bpcl, hpcl, other`.
- Customer types `domestic, commercial, industrial, government`; GST differs (domestic LPG 5%, commercial 18%, HSN 2711) [W busy.in; sources disagree on edge cases, confirm with the agency's CA]. The 14.2 kg vs 19 kg distinction is therefore also a tax and margin split.
- **Delivery-time norm.** OMC rating is by quarter: 5 star = more than 85% of deliveries within 2 days of booking, 4 star within 4 days, 3 within 6, 2 within 8; 1 star = more than 15% take over 8 days. A "Poor" quarter is fined 20% of AMDC (Average Monthly Distributor's Commission), 30% if repeated within four quarters; "Below Average" 10% / 20% [W HPCL MDG 2022 cl. 4.1 to 4.2, text extracted and read]. The repo implements this (`application/compliance/queries/get_tdt_rating.py`, tenant-configurable bands).
- **Stock mismatch is itself an irregularity.** "Mismatch between filled and empty stock although filled and empty combined stock found to be correct" counts as unaccounted sale [W HPCL MDG 2022 cl. 2.1.5]. So a filled-vs-empty reconciliation widget is a compliance control, not a nice-to-have.
- **Refill gap.** Reported norms of 25 days urban and 45 days rural; a March 2026 report of a change from 21 to 25 days was later qualified by an editor's note saying no change was made [W angelone.in, conflicting]. **Not safe to hard-code.** Treat as an open question and do not build "gap violation" widgets yet.
- **Delivery authentication (DAC).** Reported at 94.5% of deliveries by late April 2026, with a ministry floor of 80% [S ianslive.in]. The platform has its own OTP, not the OMC DAC [R `docs/research/feature-gap-analysis.md` R13, secondary]. No DAC widget until the integration exists.
- Compliance clocks: PESO licence expiry, scale certification, driver licence, vehicle documents, cylinder hydro-test due. The repo has `GET /compliance-documents?expiry=upcoming`, `is_due_for_test` on cylinder units, `license_expiry_date` on drivers, and a nightly job with `compliance_expiry_lead_days` (default 30) [R].

---

## 4. Proposed dashboard

### 4.1 Information architecture

Principle: **answers first, then evidence, then detail.** Above the fold, a user should be able to answer "is anything on fire, and is today normal?" in five seconds. Published guidance converges on this (top: status and key KPIs; middle: trends and comparisons; bottom: detail), though most of it is vendor content rather than research [S think.design, dashtemplate.com; W Carbon "Dashboards": most important data gets highest contrast and largest area, top of page].

| Zone | Purpose | Max items | Contents |
|---|---|---|---|
| 0. Control bar | Scope | 1 row | Branch, date range, comparison, saved view, live indicator |
| 1. Needs attention | Action | 6 rows + "see all" | Ranked exceptions with counts and age |
| 2. KPI strip | Status vs normal | 6 tiles | Value, delta vs comparison, 7-day sparkline |
| 3. Today's flow | Operations | 3 widgets | Pipeline, drivers, cash on the road |
| 4. Money | Finance | 2 widgets | Revenue trend, receivables ageing |
| 5. Stock | Inventory | 2 widgets | Stock by type and status, reorder proximity |
| 6. Demand and service | Planning and compliance | 3 widgets | Refills due, demand heatmap, TDT and expiries |
| Footer | Audit | 1 | Recent activity (collapsed by default) |

### 4.2 Desktop wireframe (12-column grid, 1280 px and above)

```
+--------------------------------------------------------------------------------------+
| Agency Overview   [Branch: All v] [Today v] [vs same weekday last week v] [View v] (*)Live |
+--------------------------------------------------------------------------------------+
| NEEDS ATTENTION                                                      [See all 9 >]   |
|  (!) 3 cancellations waiting for approval        oldest 2h      > /orders            |
|  (!) 4 complaints past SLA (1 critical)           oldest 1d      > /complaints        |
|  (!) 2 handovers to verify  - Rs 18,400 with drivers 1d+         > /cash-handovers    |
|  (i) 5 orders unassigned for 3h+                                 > /dispatch          |
|  (i) PESO licence expires in 21 days                             > /compliance-calendar|
+----------------+----------------+----------------+----------------+---------+--------+
| Delivered      | Collected      | Overdue        | Filled stock   | TDT     | Open   |
| 42 / ~60 ====- | Rs 1.24 L      | Rs 4.8 L       | 6.1 days       | 4 star  | compl. |
| +8% vs Tue     | -3% vs Tue     | +Rs 0.4 L wk   | 14.2kg: 4.2 d  | proj.   | 7      |
| ~~~~/\~~~~     | ~~~/\/~~~      | ~~~~~/~~~      | ~~\_~~~~       | 85.2%   | ~~~~   |
+----------------+----------------+----------------+----------------+---------+--------+
| ORDER PIPELINE (8 col)                           | CASH ON THE ROAD (4 col)          |
|  Booked    ########  12                          |  Ravi    ######  Rs 9,200  (1d)   |
|  Confirmed ####  7                               |  Suresh  ###     Rs 4,100         |
|  Assigned  ######  9     [Drivers today >]       |  Imran   #       Rs 1,200         |
|  Out       #########  14                        |  Total Rs 14,500 | review: 2      |
|  Delivered ###############  42    Failed 3       |                                   |
+--------------------------------------------------+-----------------------------------+
| REVENUE, last 30 days (6 col)          | RECEIVABLES AGEING (6 col)                  |
|  area + dashed prior period            |  0-30   ##########  Rs 3.1 L                 |
|  [day] [week]  overlay: GST? (no)      |  31-60  #####       Rs 1.2 L                 |
|                                        |  61-90  ##          Rs 0.5 L   [Top debtors >]|
+----------------------------------------+---------------------------------------------+
| STOCK BY TYPE x STATUS (6 col)         | REORDER PROXIMITY (6 col)                   |
|  14.2kg |####### filled  ## empty |dmg   |  14.2kg godown  [---o------|rp]  on hand 84 |
|  19kg   |###  filled   #### empty      |  19kg   godown  [-o-|rp]  LOW                |
+----------------------------------------+---------------------------------------------+
| REFILLS DUE (4 col)  | DEMAND HEATMAP (4 col)         | TDT + EXPIRIES (4 col)        |
|  histogram next 14d  |  7 weekdays x 24 hours         |  star distribution, 85% line  |
|  + overdue 31        |                                |  next 5 expiries timeline      |
+----------------------+--------------------------------+-------------------------------+
| Recent activity (collapsed)                                                          |
+--------------------------------------------------------------------------------------+
```

### 4.3 Mobile wireframe (under 768 px, single column)

```
+------------------------------+
| Agency Overview  [Today v]  (*)|
| Branch: All v                |
+------------------------------+
| NEEDS ATTENTION (top 3)      |
|  (!) 3 approvals        >    |
|  (!) 4 complaints late  >    |
|  (!) 2 handovers        >    |
|  See all 9                   |
+------------------------------+
| [Delivered 42/60] [Collected]|   2 x 3 grid of KPI tiles,
| [Overdue]  [Filled stock]    |   sparkline kept, delta kept,
| [TDT]      [Complaints]      |   caption hidden
+------------------------------+
| Pipeline (bars)              |   each later widget is a
| Cash on the road (list)      |   collapsible section; charts
| Revenue (sparkline + total)  |   simplify: heatmap and ageing
| Stock (bullets)              |   stacks become ranked lists
+------------------------------+
```

Rules: no horizontal page scroll, 16 px gutters, targets at least 24 by 24 CSS px (WCAG 2.2 SC 2.5.8, from the standard, not re-fetched), sparkline in tiles stays, heatmap and Sankey are hidden below 768 px and replaced by their top-3 text summary.

### 4.4 Role-based variants (default layouts keyed by permission bundle)

| Variant (trigger permissions) | Zone 1 emphasises | KPI strip | Zones kept | Zones hidden |
|---|---|---|---|---|
| **Owner** (`tenant:configure` or `invoices:read` + `routes:read` + `inventory:read`) | Approvals, past-SLA, cash, compliance | Delivered, Collected, Overdue, Filled stock, TDT, Complaints | All | none |
| **Manager** (`orders:cancel_approve`, `credit_notes:approve`) | Approvals first | Delivered, Failed, Complaints past SLA, TDT, Stock cover, Cash to verify | 1, 2, 3, 5, 6 | Receivables detail |
| **Dispatcher** (`routes:read`, no `invoices:read`) | Unassigned orders by age, failed stops | Waiting for trip, Out now, Delivered, Failed, Avg booking-to-delivery, Drivers idle | 1, 2, 3, demand heatmap, live map (later) | Money, stock detail |
| **Warehouse** (`inventory:read`, `inventory:adjust`) | Low stock, reconciliation to approve, test-due cylinders | Filled by type, Empties to return, Quarantine, Reorder breaches, Loads today | 1, 2, 5 | Money, demand |
| **Accountant** (`invoices:read`, `cash_handovers:review`) | Handovers to verify, invoices on hold, overdue | Collected, Outstanding, Overdue, On hold, Cash with drivers, GST this month | 1, 2, 4 (full), cash widget | Stock, demand, fleet |

The existing code already hides invoice and cash blocks server-side when the caller lacks `invoices:read` or the cash permissions (`include_invoices`, `include_cash`, returns `null`) [R `routers/dashboard.py`]; extend the same convention to every new section so the server never returns data a role may not see.

### 4.5 Widget contract (applies to every widget unless the spec says otherwise)

- **Shell:** a `lpg-widget` wrapper on the solid section-card surface: title (a real heading), subtitle with scope and comparison, "last updated 12 s ago", an overflow menu (View as table, Export CSV, Open full report), and a content slot.
- **States** (one state machine: `loading | ready | empty | stale | error`):
  - *loading:* skeleton at the widget's **final height** (no layout shift); the first load shows skeletons, **refreshes never do** (keep old data, show a subtle updating indicator).
  - *empty:* use `EmptyStateComponent` with a reason and a next step ("No deliveries yet today. Orders appear here once a trip is dispatched").
  - *error:* inline message, a Retry button, previous data kept if present, never a toast-only failure.
  - *stale:* if a refetch fails but old data exists, show it greyed with "Showing data from 14:02".
- **Accessibility:** heading per widget; chart is `role="img"` with a generated `aria-label` summary; a "View as table" toggle renders the same series in a real `<table>` (also the keyboard route to exact values); colour is never the only channel (labels, icons, patterns); tooltips available on keyboard focus of table rows or legend buttons; minimum 3:1 for chart marks (WCAG 1.4.11) [W W3C Understanding 1.4.11, via search summaries].
- **Refresh:** websocket "stale" event per widget (section 5.6) plus a floor of 60 s polling only where no event exists. Grafana's guidance applies: do not refresh faster than the underlying data changes [W grafana.com best practices].
- **Click-through:** every mark that represents a set of records navigates to the module page with the filter applied. **Gap:** `OrderQueue` currently reads only `create` and `customer` query params, not `status` [R `order-queue.ts:297`]; deep-link filters must be added to the target pages (Orders, Complaints, Invoices, Dispatch). That work belongs to the Home project, not an afterthought.

### 4.6 Widget catalogue (prioritised)

Verdict codes: **EXISTS** = data available from an endpoint today; **AGG** = needs a new or extended aggregation endpoint (read-only, small); **NEW** = needs data that is not captured today. Phases: **P1** MVP, **P2** next, **P3** later, **P4** blocked by the AI pause.

| ID | Widget | Chart | Verdict | Phase |
|---|---|---|---|---|
| W01 | Needs attention queue | Ranked list | EXISTS (partial) + AGG | P1 |
| W02 | KPI strip with deltas | Tiles + sparklines | AGG | P1 |
| W03 | Order pipeline | Horizontal bars | EXISTS | P1 |
| W04 | Drivers today | Stacked horizontal bars | EXISTS | P1 |
| W05 | Cash on the road | Ranked bars + age | EXISTS | P1 |
| W06 | Revenue trend vs prior | Area/line, dashed comparison | EXISTS | P1 |
| W07 | Stock by type x status | Stacked horizontal bars | AGG | P1 |
| W08 | Reorder proximity | Bullet graphs | EXISTS | P1 |
| W09 | TDT live rating | Star + distribution bars + threshold | EXISTS | P1 |
| W10 | Refills due | Histogram by due date | EXISTS | P1 |
| W11 | Receivables ageing and top debtors | Stacked bars + ranked list | AGG | P2 |
| W12 | Demand heatmap | Weekday x hour heatmap | AGG | P2 |
| W13 | Failed-delivery reasons | Ranked bars | AGG | P2 |
| W14 | Compliance timeline | Timeline / calendar strip | AGG | P2 |
| W15 | Complaints by age vs SLA | Stacked bars by category | AGG | P2 |
| W16 | Revenue mix | 100% stacked bar by customer or cylinder type | AGG | P2 |
| W17 | Empty vs filled reconciliation | Diverging bars (variance) | EXISTS (partial) | P2 |
| W18 | Collections by method | Stacked columns by day | AGG | P2 |
| W19 | Cylinder flow (godown, van, customer, empties, OMC) | Sankey | AGG | P3 |
| W20 | Live fleet map | Map with markers | AGG (Redis) | P3 |
| W21 | Trip utilisation | Dot plot: loaded vs capacity | AGG | P3 |
| W22 | Branch comparison | Small multiples | AGG | P3 |
| W23 | Repeat-customer / refill cadence | Cohort grid | AGG | P3 |
| W24 | Anomaly bands, forecast, narrative insight | Line with band, text | NEW + AI | P4 |

### 4.7 Widget specifications

Common states, a11y and refresh come from 4.5; only differences are listed.

**W01 Needs attention queue (P1).** *Question:* what is waiting on me right now? *Chart:* a ranked list, not a chart, because the output is an action, not a quantity; each row shows severity icon, count, label, oldest age and a link. *Data:* `pending_cancellations`, `failed_today`, `open_complaints`, `low_stock_count`, `on_hold_count`, `handovers_awaiting_review`, `cash.awaiting_handover` are EXISTS in `GET /dashboard/operations`. Complaints past SLA (`complaint.sla_due_at < now`), orders unassigned over N hours, compliance expiring within the lead days and test-due cylinders (`is_due_for_test`) need **AGG** (`GET /dashboard/attention`). *Interactions:* row click goes to the filtered module; rows ranked server-side by severity then age; permission-gated rows. *Refresh:* on `dashboard.metrics_stale`. *Empty:* "Nothing needs you. Last check 14:02" (an empty queue is the success state, say so).

**W02 KPI strip (P1).** *Question:* is today normal? *Chart:* tile with big number, delta chip (arrow plus sign plus text, never colour alone), 7-day sparkline (existing inline-SVG polyline in `StatCard`), caption naming the comparison. Delivered shows a progress bullet only if a target or baseline exists. *Data:* AGG `GET /dashboard/overview?range&compare&branch` returns `{kpi, value, previous, series[]}`. Series come from `orders.order_status_history` (deliveries per day), `accounting.invoice`/`payment` (revenue, collections), complaint counts. `GET /reporting/sales` already gives daily revenue per branch [R]. *Interactions:* tile is a real link to the module (existing `route` input), hover shows the exact comparison values, keyboard focus does the same. *Comparison default:* same weekday last week (LPG demand has a strong weekday pattern [U], so day-over-day is misleading).

**W03 Order pipeline (P1).** *Question:* where are today's orders stuck? *Chart:* horizontal bars ordered by lifecycle with value labels, because bars compare lengths accurately and the order is a process, not a share of a whole. Not a funnel in P1: the data is a current-state snapshot (`open_by_status`), not a cohort conversion, and a funnel would imply conversion rates that are not computed [R `order_pipeline`]. A true funnel (booked to delivered by cohort) is P2 using `order_status_history`. *Data:* EXISTS `orders.open_by_status`, `delivered_today`, `failed_today`. *Interactions:* click a bar to open Orders filtered by status; hover shows oldest order age (AGG, small). *Empty:* "No open orders."

**W04 Drivers today (P1).** *Question:* who is on track, who is failing? *Chart:* one stacked horizontal bar per driver (delivered / pending / failed), because three parts of a small whole per category read well and drivers are comparable on a common axis. Labels on bars so colour is not the only cue. *Data:* EXISTS `GET /reporting/drivers?start_date&end_date&branch_id` returns `delivered_stops, failed_stops, total_stops, cash_expected, cash_handed_over, cash_accuracy` per driver per day [R]. *Interactions:* click opens that driver's active trip in Dispatch (`?trip=` is already read by the dispatch page [R]); toggle "show cash accuracy". *Empty:* "No trips today."

**W05 Cash on the road (P1).** *Question:* how much cash is with whom, for how long? *Chart:* ranked horizontal bars of cash per driver with the age of the oldest route as a text badge. *Data:* EXISTS `GET /cash-handovers/cash-in-hand` (`cash_amount`, `upi_amount`, `oldest_route_date`, `route_count`, `stop_count`) and `GET /cash-handovers/cash-book?date` (collected by method, handed over, accepted, shortfall, excess, pending) [R]. *Interactions:* click opens Cash handovers filtered to the driver. *Visibility:* only with the cash permissions (server returns null otherwise).

**W06 Revenue trend vs prior (P1).** *Question:* is revenue above or below normal? *Chart:* area for the selected range plus a dashed line for the comparison period; direct end labels; no dual axis. *Data:* EXISTS `GET /reporting/sales?start_date&end_date&branch_id` (per day: `total_revenue`, `taxable_value`, `total_tax`, `total_invoices`). Show taxable value as the headline and GST separately so the owner does not mistake collected GST for income [R]. *Interactions:* hover crosshair with both periods; click a day to drill to Invoices with that issue date (`issued_from`/`issued_to` params exist on `GET /invoices` [R]); day/week toggle. *Empty:* "No invoices in this period."

**W07 Stock by type and status (P1).** *Question:* how many cylinders of each kind do I have and in what state? *Chart:* one stacked horizontal bar per cylinder type (filled, empty, damaged/leak/quarantine grouped, in transit on vans), replacing the 7-slice doughnut. Optional toggle: godown vs vehicles. *Data:* **AGG** `GET /dashboard/stock?group_by=cylinder_type,status,location_type`; today only totals exist (`inventory_by_status`) and per-location balances need N calls (`GET /inventory-locations/{type}/{id}/balance`), which is exactly the N+1 the summary endpoint was written to avoid [R `routers/dashboard.py` docstring]. *Interactions:* click a segment to open Inventory with `type`, `id`, `cylinder_type_id` (these params are read by the inventory page [R `feature-inventory.ts:464`]).

**W08 Reorder proximity (P1).** *Question:* which locations are close to or below reorder point? *Chart:* bullet graphs (current quantity bar, reorder-point marker, safety-stock marker, qualitative bands). Stephen Few designed bullet graphs specifically to replace dashboard gauges, using a quantitative scale starting at zero with optional ranges [S perceptualedge.com]. *Data:* EXISTS `GET /inventory/reorder-signals` (`on_hand`, `reorder_point`, `safety_stock` per location and type), but it only returns **currently breached** thresholds, so "close to" needs AGG (`?include_near=true`). *Days of cover* (on hand / average daily deliveries) is AGG from delivery transactions.

**W09 TDT live rating (P1).** *Question:* if the quarter ended now, what star rating would I get, and how much headroom do I have? *Chart:* big star count, stacked bar of orders by delivery-day band, a marker at the 85% threshold of the band that decides the rating, and a "days left in the quarter" caption. *Data:* EXISTS `GET /tdt-rating/live-projection?branch_id` returns `overall_stars`, `distribution[{stars, order_count}]`, `total_orders`, quarter bounds [R]; bands and fines are tenant-configurable in `tdt-rating-config`. Exact rule per HPCL MDG 2022 [W]. *Note:* the OMC portal's own figure is authoritative and excludes events beyond control (cl. 4.2 ii); label this "projection". *Interactions:* click opens `/reports/tdt-rating`. Fine impact in rupees needs AMDC, which is not captured (Q5).

**W10 Refills due (P1).** *Question:* how much repeat demand is coming, and who have I missed? *Chart:* histogram of `refill_due_date` over the next 14 days plus an "overdue" bar at the left, because a time distribution is the question. *Data:* EXISTS `GET /customers/refill-due?within_days=` returns `refill_due_date`, `interval_days`, `last_delivered_at`, customer and phone. Group client-side. It is a heuristic (`refill_heuristic_v1`), not an LLM feature; label it "predicted" [R `home.ts` comment]. *Interactions:* click a bar opens Customers filtered to that due window with a "Book" action (`?create=true&customer=` exists [R]). **Check Q9:** confirm the AI pause does not cover this deterministic heuristic.

**W11 Receivables ageing and top debtors (P2).** *Question:* where is money stuck and who owes it? *Chart:* stacked horizontal bars for 0-30 / 31-60 / 61-90 / 90+ days, splittable by customer type, plus a ranked list of the top 10 debtors; sequential single-hue ramp (older is darker), because ageing is an ordered quantity. *Data:* **AGG** `GET /dashboard/receivables-aging`. The repository already has `get_outstanding_balances` but no endpoint exposes it, and today's snapshot defines overdue as `issued_at < now - payment_terms_days` with no buckets [R]. *Interactions:* click bucket opens Invoices with status and age filter; click debtor opens that customer's ledger (`/ledger/:customerId` [R]). Customer names are PII: gate with `ledger:read`.

**W12 Demand heatmap (P2).** *Question:* when do bookings arrive, so I can staff phones and trips? *Chart:* 7 weekdays by 24 hours heatmap, single-hue sequential colour, direct value in a tooltip and via the table fallback; calendar heatmap (day-by-day, GitHub style) as a second view for seasonality. *Data:* **AGG** `GET /dashboard/demand-heatmap?from&to&metric=bookings|deliveries` grouped on `orders.order.created_at` in IST. Minimum 4 weeks of data to be meaningful [U]. *A11y:* heatmaps are weak for screen readers; the table fallback is mandatory.

**W13 Failed-delivery reasons (P2).** *Question:* why do deliveries fail, and is it fixable? *Chart:* ranked horizontal bars of the five reason codes (not a pie). *Data:* **AGG**; reason codes exist in the domain, the reason text is in order status history [R `domain/order/order.py`]. *Interactions:* click opens failed orders; "reschedule" actions live on Orders.

**W14 Compliance timeline (P2).** *Question:* what expires in the next 90 days? *Chart:* horizontal timeline with items on a date axis, coloured by days-left band (icon and label as well), grouped by owner type (agency, godown, driver, vehicle, scale, cylinder tests). *Data:* **AGG** `GET /dashboard/compliance-timeline?horizon_days=90` merging `compliance-documents` (expiry), `drivers.license_expiry_date`, scale certificates and `cylinder-units.test_due_date`. Today the calendar page does N lookups (documents, drivers, vehicles, warehouses) client-side [R `feature-compliance-calendar.ts`]. *Interactions:* click opens the Compliance Calendar at that item. PESO licences lapse on 30 September for Form E/F/G holders [S, `docs/research/feature-gap-analysis.md` R4, secondary].

**W15 Complaints by age vs SLA (P2).** *Question:* which complaints will breach SLA? *Chart:* stacked bar by category (7 categories: ShortDelivery, DamagedCylinder, BillingDispute, DriverConduct, LateDelivery, GasLeakSafety, Other) split by "on time / due in 4 h / overdue". *Data:* **AGG** from `complaint.complaint` (`sla_due_at`, `status`, `priority`, `category`) [R]. *Safety rule:* GasLeakSafety items always appear in the attention queue regardless of count.

**W16 Revenue mix (P2).** *Question:* which cylinder type or customer segment drives revenue? *Chart:* 100% stacked bar over time or a sorted bar; **no pie/donut** (more than three categories). Treemap only if cylinder types exceed ~8. *Data:* **AGG** from `accounting.invoice_line` by cylinder type and customer type [R invoice lines exist].

**W17 Empty vs filled reconciliation (P2).** *Question:* do the books match the floor, per cylinder type? *Chart:* diverging bars of `variance` (actual minus expected) centred on zero, with pending-approval state. *Data:* EXISTS `GET /inventory-locations/{type}/{id}/reconciliation-records` returns `expected_quantity, actual_quantity, variance, state` per location; a tenant-wide list needs **AGG**. Compliance relevance: MDG cl. 2.1.5 [W].

**W18 Collections by method (P2).** *Question:* how are customers paying? *Chart:* stacked columns per day by method (cash, upi, card, online_gateway, credit). *Data:* **AGG**: the cash book covers one `date` per call [R].

**W19 Cylinder flow Sankey (P3).** *Question:* where do cylinders go, and do empties come back? *Chart:* Sankey OMC to godown to vans to customers and empties back to godown to OMC. A Sankey earns its place here because the quantity is a conserved flow across stages; keep it to one period and at most ~12 nodes. *Data:* **AGG** from `inventory.inventory_transaction` types `grn_receipt, load, delivery, collection, omc_return` [R]. *A11y:* table fallback is the primary path.

**W20 Live fleet map (P3).** *Question:* where are my vans and what is the next stop? *Chart:* map with van markers and stop pins; Leaflet 1.9.4 (BSD-2) or MapLibre GL 6.19 (BSD-3) [W]. *Data:* driver location is held in Redis (`RedisDriverLocationStore`, `POST /routes/{id}/location`) and exposed per order (`GET /orders/{id}/tracking`); delivery addresses carry latitude and longitude [R]. A tenant-wide "all active vans" read is **AGG**. **Map tiles:** the OSM community tile servers prohibit heavy or commercial reliance and offer no SLA; budget a tile provider or self-hosting [W operations.osmfoundation.org].

**W21 Trip utilisation (P3).** Loaded cylinders vs `vehicle.capacity_units` per trip, dot plot; **AGG**. Cost per trip, fuel and driver pay are **NEW** (not captured).

**W22 Branch comparison (P3).** Small multiples (same chart, one per branch, shared axes) for revenue and deliveries; the reporting endpoints already accept `branch_id` [R]; the operations endpoint does not.

**W23 Repeat customers (P3).** Cohort grid of customers by first-delivery month vs refill cadence; **AGG** from `reporting/consumption` (`avg_refill_interval_days` per customer, backed by a materialised view) [R].

**W24 Insights and forecasts (P4, paused).** Anomaly bands, forecast ranges and narrative summaries. The owner paused AI automation on 2026-11-19, so none of this is in scope. When revisited, follow the pattern in Tableau Pulse: deterministic statistics produce the facts, language is layered on top [S help.tableau.com].

### 4.8 What to remove from Home

Customers, Drivers, Fleet Vehicles and Godowns tiles; Fleet Status bar chart; Inventory-by-status mini-cards; Cylinder Prices card (move to Settings > Price list); the doughnut. The data stays reachable in their modules.

---

## 5. Interaction model

1. **Global controls** (sticky below the header): date range presets (Today, Yesterday, Last 7 days, Last 30 days, Month to date, FY to date) and a custom range using the existing `date-range-filter` component [R `libs/shared/ui/src/lib/filter-bar`]. **Comparison selector:** previous period, same weekday last week (default), same period last year. Widgets inherit the global range unless pinned (for example "Today" for the pipeline).
2. **Branch filter.** Visible only to multi-branch tenants and to roles with cross-branch visibility, matching `docs/ui/06-dashboard-layout.md`. Reporting endpoints take `branch_id`; `GET /dashboard/operations` does not, so the new overview endpoints must.
3. **State in the URL.** `?range=7d&cmp=wow&branch=<id>` so a view can be shared, bookmarked and tested. Per-viewer conveniences (collapsed widgets, last view) go in `localStorage` with try/catch fallbacks, as `SetupChecklist` already does.
4. **Cross-filtering, restrained.** Power BI's default of "every visual cross-filters every other" is powerful but confusing for non-analysts [W learn.microsoft.com]. Recommendation: **drill-through, not cross-filter, on Home.** Clicking a mark navigates to the module with the filter applied. Allow one explicit in-page cross-filter at most: selecting a driver in W04 highlights that driver in W05. Full cross-filtering belongs in a future analytics page.
5. **Saved views.** P2: named presets (range, comparison, branch, collapsed widgets) stored locally; P3: server-side per user (needs a preferences endpoint; none verified in `my-profile`).
6. **Real-time.** The websocket already carries `dashboard.metrics_stale`, `order.status_changed`, `delivery.route_updated`, `driver.updated`, `notification.new` [R `realtime_handlers.py`]. Replace "refetch everything after 1 s" with an event-to-widget map: `order.status_changed` stales W01 to W04 and W02; `delivery.route_updated` stales W04, W05; inventory events stale W07 and W08. Updates swap data in place with a 150 ms fade (instant when reduced motion), show "updated just now" and never replace content with skeletons. On reconnect, refetch what was missed (already done today). Use the existing `lpg-live-indicator`.
7. **Customisation.** P3, and only a constrained version: reorder and hide widgets in a fixed 12-column grid with three sizes (S, M, L), using the Angular CDK drag-drop already installed. Free-form resize (gridstack 14.1.1 MIT, has an Angular wrapper [W unpkg]) is not recommended: it multiplies the combinations to test across three themes and breakpoints. Admin-defined defaults per role come first; per-user overrides second.
8. **Keyboard.** Control bar and widgets reachable in DOM order; widget menus open on Enter; "View as table" toggles with Space; the command palette already exists, add "Go to widget".

---

## 6. Visual design system for charts

### 6.1 Token strategy

The design system has no chart tokens today [R]. Add a `semantic.color.chart` group to `design-tokens/tokens.json` with `light`, `dark` and `highContrast` values (the generator already emits CSS, TypeScript and Dart from this one file, so the mobile apps can reuse them):

| Token group | Purpose | Rule |
|---|---|---|
| `chart.series.1..6` | Categorical (branches, drivers, cylinder types) | At most 6; beyond that group into "Other" or use small multiples. Never reused for status. |
| `chart.seq.1..7` | Sequential (heatmap, ageing) | One hue (gasBlue ramp), lightness-ordered. Dark theme inverts the meaning (lightest = largest), as Carbon does [W]. |
| `chart.div.neg/neutral/pos` | Diverging (variance, delta) | Blue to neutral to orange rather than red/green so CVD users keep the distinction; sign also in text. |
| `chart.status.*` | Alias of `status.success/warning/danger/info` | Only for things that **are** statuses (damaged, overdue, failed). |
| `chart.axis`, `chart.grid`, `chart.label`, `chart.surface` | Chrome | `grid` is the existing `border.default`; `label` is `text.secondary`. |
| `chart.comparison` | Prior-period line | Neutral grey, dashed. |

**Candidate categorical palette (proposal, must be validated):** start from colour-blind-safe sets, the Okabe-Ito eight (`#0072B2` blue, `#E69F00` orange, `#009E73` bluish green, `#D55E00` vermillion, `#56B4E9` sky, `#CC79A7` purple, `#F0E442` yellow, black) [S via search-result summaries; cite Wong 2011 and Okabe-Ito 2008 for a paper-grade source] or Paul Tol "bright" (`#4477AA #EE6677 #228833 #CCBB44 #66CCEE #AA3377 #BBBBBB`) [S, khroma README]. Adapt so series 1 is brand gasBlue (`#162b66` light, `#6c8ddb` dark, existing primitives), and exclude hues that read as status (green/amber/red) from the categorical set, since the design doc forbids reuse for status. **Validation gate (CI):** a Jest test that reads `tokens.json`, computes WCAG contrast of every chart mark token against `surface.base`, `surface.raised` and `surface.overlay` for each theme and asserts at least 3:1 (WCAG 1.4.11), plus an offline colour-vision-deficiency simulation script reviewed once per palette change.

**High-contrast theme.** The `highContrast` theme uses white surfaces, black text and `hcBlue`/`hcYellow` primitives [R tokens]. For charts, switch on `aria.decal` patterns in ECharts (documented) so series differ by texture and not hue, thicker lines (2 px to 3 px), and direct labels instead of legends [W echarts aria docs].

**Tenant branding must not reach charts.** The colour-system doc already gates tenant colours through contrast checks; chart tokens should not be tenant-overridable at all.

### 6.2 Marks, type and spacing

- **Typography:** use existing `--typography-*` tokens; chart text is `caption` (axis, ticks) and `label` (series names); KPI numbers use `heading2/3` with tabular numerals (`font-variant-numeric: tabular-nums`) so digits do not jitter on refresh.
- **Numbers:** Indian grouping and compact units. `formatCurrencyInr` already uses `en-IN` [R `format.ts`]; for axes, `Intl.NumberFormat('en-IN', {notation:'compact'})` should yield "L" and "Cr" units [U, confirm in a browser before relying on it]. Always show full value in the tooltip.
- **Spacing:** widget padding from `--spacing-lg`, gap between widgets `--spacing-lg`, internal chart margins `--spacing-md`.
- **Motion:** use the token durations (`micro 100 ms`, `small 150 ms`, `medium 250 ms`) and easing; under `prefers-reduced-motion` set chart `animation: false` and let the existing `reducedMotion` token set apply (0 ms to 50 ms). No animated blur. Number count-up is off.
- **Reading chart colours at runtime.** ECharts options cannot take CSS variables directly. The wrapper resolves tokens via `getComputedStyle(el)` and re-resolves on theme change, observing `data-theme` and `class` on `html` and `body` (the logic `home.ts` has, done once, with a single disconnecting observer).

### 6.3 Glass and surfaces

Widgets sit on the solid `section-card` surface with the existing border (section 2.3). Tooltips and drill-down popovers use the existing frosted popover surface automatically (`.p-popover` family). Grain stays off charts. Do not put chart marks on translucent surfaces: the blur and grain reduce effective contrast and make the 3:1 mark rule untestable.

### 6.4 Chart choice table

| Use | Avoid | Why |
|---|---|---|
| Horizontal bars for rankings and category comparison | Pie/donut with more than 3 slices | Length judged more accurately than angle; many slices cannot be labelled or contrast-checked [S datawrapper.de pie guidance] |
| Line/area for time with comparison line | Dual y-axes | Different scales invite false correlation; use indexed lines or small multiples [S datawrapper.de dual-axis guide] |
| Stacked bars (2 to 4 parts) for composition | Stacked area with more than 4 series | Hard to read middle series; Grafana warns stacking can mislead [W] |
| Bullet graphs for value vs target/reorder point | Radial gauges and speedometers | Few's bullet graph replaces gauges, takes less space and starts at zero [S perceptualedge.com] |
| Heatmap for two categorical axes (weekday x hour) | 3D charts, ever | Distort magnitude |
| Sparkline in a KPI tile | Sparkline with axes | Context, not reading |
| Sankey for conserved flows | Sankey for more than ~12 nodes | Unreadable, poor a11y |
| Treemap only for many parts of a whole | Treemap for a few categories | A sorted bar is clearer |

---

## 7. Trends: what the current practice says, and what applies to us

I searched for 2025 to 2026 material. **Caution:** most dashboard-design articles that surfaced are vendor blogs, not research, and I could not open first-party design write-ups for Stripe, Vercel or Shopify dashboards. Treat the trend list as informed convention, not evidence of effect.

| Trend | Evidence | Applies? | Decision |
|---|---|---|---|
| **Answers first** (key status on top, trends middle, detail bottom); one primary question per dashboard, answerable in seconds | Think.design, DashTemplate, UXPin [S]; Carbon: highest contrast and area to the most important data, top of page [W] | Yes | Zones 1 and 2 |
| **KPI tiles with comparison, delta and sparkline**; treat the change as primary | Improvado, Guljarhosen, Stripe Home charts with comparison range [S] | Yes | W02. Keep sparklines on desktop and tablet, trim on mobile |
| **Limit metrics per view** | Improvado (5 to 9), Boundev (5 to 7; 3 to 5 executive) [S], Carbon "limit the number of metrics" [W] | Yes | 6 KPI tiles, 6 attention rows, about 12 widgets in total across all roles but at most about 8 visible per role |
| **Bullet graphs over gauges** | Few spec [S] | Yes | W08, optionally W09 |
| **Heatmaps for time-of-day demand and area/lane problems** | Cursa logistics guide, Dashtera case study [S] | Yes | W12 |
| **Funnels for pipeline conversion** | Convention | Partly | Pipeline bars in P1 (snapshot data); funnel in P2 once cohort data exists |
| **Sankey for flows** | Convention | Yes, later | W19, P3 |
| **Maps for fleet and delivery density** | Fleet dashboards (FleetRabbit, AdminLTE roundup) [S] | Later | W20, P3, needs tile provider |
| **Role-based and audience-scoped dashboards** | Grafana: each dashboard answers a specific question or tells a story [W]; Boundev "design pages around specific users" [S] | Yes | 4.4 |
| **Customisable widget grids, saved views** | Stripe: add, remove, reorder Home widgets [S]; Linear Insights: flexible dashboards, shared or private [S linear.app/docs/insights] | Partly | Constrained customisation in P3 |
| **Cross-filtering and drill-through** | Power BI visual interactions [W] | Drill-through yes, global cross-filter no | Section 5 |
| **Real-time streaming updates** | Grafana: do not refresh faster than data changes [W] | Yes, event-driven | Section 5.6 |
| **Skeleton and empty states; avoid layout shift** | web.dev CLS [W] | Yes | 4.5 |
| **Narrative, anomaly and "pulse" summaries** | Tableau Pulse: stats detect facts, language layered on top, digests by email or Slack [S help.tableau.com] | Future only | Paused by owner; W24 |
| **Accessible charts: data-table alternative, keyboard, not colour-only** | Chartability heuristics (50 testable heuristics, built on WCAG) [S chartability.fizz.studio]; WCAG 1.4.11 3:1 for graphical objects [S W3C]; already in `docs/ui/17-accessibility.md` section 9 [R] | Yes, mandatory (WCAG 2.2 AA is a Phase 1 requirement per AGENTS.md) | 4.5, 10 |
| **Colour-blind-safe, dark-mode-aware palettes** | Carbon palettes: categorical, sequential (inverts in dark), diverging, alert [W]; Okabe-Ito [S] | Yes | 6.1 |
| **Mobile-first dashboards** | Boundev: sparklines in cards, drill-down as main interaction [S] | Yes for owner | 4.3 |
| **Canvas vs SVG, decimation, lazy chart bundles** | ECharts supports both renderers [W echarts import docs] | Yes | Section 8 |
| **Dribbble/Behance/Mobbin-style visual galleries** | Not opened | n/a | Use only as visual inspiration; none cited as evidence |
| **Dense "command centre" dark dashboards, neon glow** | Visual trend, no evidence of usefulness | No | Conflicts with the paper/glass brand and high-contrast requirement |

**What makes the good ones work (common denominator across the sources I could verify):** a small number of numbers, each with its comparison; one hierarchy of size and contrast; consistent colour meaning across the page (Carbon: "keep colours consistent for each data set across the dashboard" [W]); every number is a way in, not a dead end; the page is scoped to an audience question, not to "all the data".

**Domain-specific chart types worth having:** weekday-by-hour demand heatmap; reorder bullets per cylinder type; empties-return flow (Sankey); driver cash ageing (bars); delivery-days distribution against the 2/4/6/8 day bands (stacked bar with threshold); expiries timeline. Not worth having: gauges for stock, pies for status, 3D, radar for driver comparison.

---

## 8. Library recommendation

### 8.1 Comparison

| Criterion | **Apache ECharts 6.1** | Chart.js 4.5.1 (PrimeNG `p-chart`, **installed**) | AG Charts Community 14.x | ApexCharts 8.x | Highcharts | D3 | Leaflet / MapLibre |
|---|---|---|---|---|---|---|---|
| Licence | Apache-2.0 [W] | MIT [W] | MIT; Enterprise is commercial per developer [W] | Free only for orgs under US$2M revenue/funding; OEM licence needed to embed in a product others configure [W] | Commercial, about US$366 per developer seat for Core; SaaS and OEM tiers [W] | ISC | BSD-2 (Leaflet 1.9.4) / BSD-3 (MapLibre 6.19.0) [W] |
| Fits a multi-tenant SaaS without legal review | Yes | Yes | Yes (Community only) | **No, needs sales contact** | Needs SaaS licence | Yes | Yes (tiles are separate) |
| Chart coverage for this plan | All needed: bar, line, area, heatmap, calendar, funnel, gauge, Sankey, treemap, markLine/markArea, dataZoom, brush [W echarts feature page, S] | Core types; heatmap via `chartjs-chart-matrix` 3.1.0, Sankey via `chartjs-chart-sankey` 0.19.1, annotation via plugin [W unpkg] | Bar, line, area, scatter, bubble, pie, donut, combination. **Heatmap, treemap, sunburst, Sankey, gauges, waterfall are Enterprise**; maps Enterprise; zoom Enterprise [W] | Broad | Broad | Anything, built by hand | Maps only |
| Bundle (gzip) | Tree-shaken from `echarts/core`; **TanStack's controlled suite puts a line/bar/area/scatter ECharts consumer at 157 to 177 kB** [W, vendor benchmark]; full package much larger. Our figure **not measured**; spike required | Existing chunk: 77.6 kB gzip (all types registered via `chart.js/auto`) [R]; tree-shaken bar/line only about 46 to 60 kB per TanStack [W] | Package about 367 kB gzip main export per Bundlephobia [W] | About 164 kB [W] | About 100 kB [W] | Modular; pay per module | Leaflet small (unverified); MapLibre large (unverified) |
| Theming via CSS tokens | Via JS option; wrapper resolves tokens on theme change (as `home.ts` does) | Same | Theme API | Same | Same | Full control | n/a |
| Accessibility | `aria.show` generates `aria-label`; **decal patterns** for colour-blind users [W]; no documented keyboard navigation (gap, wrapper must provide table and legend buttons) | Canvas only; you add `role="img"`, `aria-label`, fallback content [W] | Keyboard navigation and screen-reader support in Community [W] | ARIA present [U] | Best-in-class accessibility module, paid [U] | DIY | Markers can be real DOM (Leaflet) |
| Renderer | Canvas or SVG, chosen per import | Canvas | Canvas | SVG | SVG | SVG/Canvas | DOM/canvas |
| Angular 22 / signals | `ngx-echarts` 22.0.0 peer `@angular/core >=22.0.0`, `echarts >=5.0.0` [W]. Or direct use (no wrapper dependency) | PrimeNG 22 wrapper installed [R] | `ag-charts-angular` 14.3.0, peer Angular >=20 [W] | `ng-apexcharts` | official wrapper | n/a | wrappers exist [U] |
| Maintenance | Apache project, 6.1.0 current [W] | 4.6.1 current (repo pinned at 4.5.1) [W] | Active (14.3.0) [W] | Active (v8) [W] | Active | Active | Active |

Rejected: **AG Charts Community** (the heatmap, gauge, Sankey and treemap the plan needs are Enterprise, and ADR-028 allows Enterprise only per feature with a documented requirement and licence); **ApexCharts** (licence thresholds and OEM wording make this a procurement problem for a multi-tenant SaaS); **Highcharts** (cost and licence terms, though its accessibility is the strongest; revisit only if ECharts fails the accessibility spike); **D3** (only for a bespoke piece if ECharts cannot do it; none identified); **ngx-charts** (25.0.3, MIT, supports Angular 21.2 and 22 [W], but SVG-only with fewer chart types and no heatmap-calendar or Sankey).

### 8.2 Recommendation

**Primary: Apache ECharts via our own thin wrapper.** One library covers every widget in P1 to P3 except the map. Apache-2.0 removes licensing risk. SVG rendering gives crisp, printable charts and DOM that can be inspected by tests. Decal patterns address the high-contrast theme. A directly-owned wrapper (about 150 lines: `input()` signals for option and theme, `ResizeObserver`, token resolution, a11y summary and table fallback, dispose on destroy) avoids depending on a wrapper's release cadence for each Angular major. `ngx-echarts` 22.0.0 is a verified drop-in if the team would rather not own the wrapper [W].

**Fallback: Chart.js, already installed.** Keep `chart.js` and add `chartjs-chart-matrix` (heatmap) and `chartjs-plugin-annotation` (target lines); register only the controllers used, rather than `chart.js/auto`. Costs: no native Sankey, treemap, gauge or calendar; canvas-only, so all a11y is ours; but zero new dependency and the smallest bundle. Choose this if the spike shows the ECharts chunk is unacceptable for Home.

### 8.3 How it plugs into the Nx workspace

1. New secondary entry point `libs/shared/ui/src/charts.ts`, path alias `@lpg/shared/ui/charts` in `tsconfig.base.json`, mirroring `data-grid.ts` and `app-shell.ts` (both of which exist because importing the main barrel dragged AG Grid into the initial bundle, see the comments in those files [R]). **Do not re-export charts from `index.ts`.**
2. Contents: `ChartComponent` (wrapper), `WidgetShellComponent`, `buildOption` mappers (pure functions, one per widget type: ranked-bar, stacked-bar, time-series, heatmap, bullet, timeline), `chart-theme.ts` (token resolver), `chart-table.component.ts` (the "View as table" fallback). Sparklines stay as inline SVG in `StatCard` (no library).
3. Import ECharts modules explicitly: `echarts/core`, `BarChart`, `LineChart`, `HeatmapChart`, components `GridComponent`, `TooltipComponent`, `LegendComponent`, `MarkLineComponent`, `VisualMapComponent`, `CalendarComponent`, `AriaComponent`, `DatasetComponent`, and **`SVGRenderer`** only [W echarts import docs: renderers are not included by default, and `AriaComponent` must be imported or `aria.show` has no effect].
4. Split into two lazy chunks: **core** (bar, line, heatmap, bullet via custom series or bar+markLine) loaded by Home, and **advanced** (Sankey, treemap, geo) loaded only by the widgets that use them.
5. On Home, defer the chart chunk: `@defer (on viewport; prefetch on idle)` with a fixed-height skeleton, so KPI tiles, the attention queue and sparklines (no library) paint first.
6. Nx boundaries: `scope:shared` may not depend on feature libs (existing `enforce-module-boundaries` rule); widgets live in a new `libs/dashboard/feature-home` (or stay in `apps/dashboard/src/app/home` for P1) and consume only `@lpg/shared/ui/charts` and `@lpg/shared/data-access`.

### 8.4 Bundle-impact approach and estimate

- **Facts [R]:** `main` is 354,314 B raw / 67,696 B gzip in the existing `dist`; the Chart.js chunk is 77.6 kB gzip; AG Grid was moved to a secondary entry for exactly this reason. I did not rebuild, and I could not confirm the owner's statement that the initial total exceeds 700 kB (the `dist` may predate recent changes). Initial budget is warning 700 kb / error 1 mb [R `apps/dashboard/project.json`].
- **Estimate [U]:** ECharts tree-shaken to the set above, SVG renderer, about 130 to 190 kB gzip as a lazy chunk (proxy: TanStack suite range). That is roughly 50 to 110 kB gzip more than the Chart.js chunk that Home loads today, **off the initial budget**, but on the Home critical path for users who land there (most do).
- **Mitigation:** `@defer`, `modulepreload` hint after first paint, shared chunk with Settings pages that need charts later, and a per-chunk budget (`anyScript` type in `project.json` budgets) to stop silent growth [budget type name from Angular CLI docs, not re-verified].
- **Day-one spike (do before committing):** build a minimal ECharts bundle with the import list above, report raw/gzip next to `chunk-ASQHT8e5.js`, and test a low-end device profile. If the chunk exceeds about 200 kB gzip, take the fallback.
- **Remove after migration:** PrimeNG `ChartModule` usage in `home.ts`; one more consumer remains in `libs/admin/feature-license/.../license-issuance-page.ts` [R grep]. Migrate it later, then drop `chart.js` if nothing else needs it.

---

## 9. Backend and API work

All new endpoints sit under `/api/v1/dashboard/*`, code-first in FastAPI, regenerated into the committed OpenAPI spec and TypeScript client (`npm run generate:api-client`, ADR-026). They follow the existing pattern: read-model use case in `application/dashboard/`, reader protocol, SQL reader in `infrastructure/persistence/repositories/dashboard.py`, tenant-scoped session (RLS on), IST business day (`_IST`, `_BUSINESS_TZ` already used).

| # | Endpoint | Request | Response (brief) | Serves | Notes |
|---|---|---|---|---|---|
| 1 | `GET /dashboard/overview` | `from, to, compare=prev\|wow\|yoy, branch_id?` | `kpis: [{key, value, previous, delta_pct, series: [{date, v}]}]` | W02 | Single composed read; replaces counting calls in `/operations` for the strip |
| 2 | `GET /dashboard/attention` | `branch_id?` | `items: [{key, severity, count, oldest_at, link}]`, ranked | W01 | Section-null for missing permissions |
| 3 | `GET /dashboard/delivery-performance` | `from, to, branch_id?, group_by=driver\|day\|reason` | stops by status, failed reasons, delivery-day distribution | W04, W13 | `GET /reporting/drivers` already covers drivers; this adds reasons and avg booking-to-delivery |
| 4 | `GET /dashboard/stock` | `branch_id?, group_by=cylinder_type,status,location_type, include_near=bool` | rows `{cylinder_type_id, status, location_type, qty}` plus `days_of_cover` per type | W07, W08 | Replaces `inventory_by_status` totals |
| 5 | `GET /dashboard/receivables-aging` | `as_of?, customer_type?, branch_id?, top=10` | buckets and `top_debtors[{customer_id, name, amount, oldest_days}]` | W11 | `ledger:read`/`invoices:read` only |
| 6 | `GET /dashboard/collections` | `from, to` | per day by method, handed over, shortfall | W18, W05 | Extends cash-book across days |
| 7 | `GET /dashboard/demand-heatmap` | `from, to, metric, branch_id?` | 7 x 24 matrix | W12 | Precompute (hourly materialised view) |
| 8 | `GET /dashboard/compliance-timeline` | `horizon_days=90` | items `{owner_type, owner_label, doc_type, expiry_date, days_left}` | W14, W01 | Merges four sources server-side |
| 9 | `GET /dashboard/complaints-sla` | `branch_id?` | counts by category and SLA band | W15 | |
| 10 | `GET /dashboard/cylinder-flow` | `from, to` | nodes and links | W19 (P3) | From `inventory_transaction` |
| 11 | `GET /dashboard/fleet-live` | `branch_id?` | active routes with last location and next stop | W20 (P3) | Reads the Redis location store |

**Cross-cutting rules**

- **Tenant isolation.** Every query runs on the tenant-scoped session so RLS applies; never trust a `tenant_id` in the request. Add tenant-isolation tests per endpoint (AGENTS.md requires them for anything touching tenant-scoped data).
- **Caching.** Redis result cache with a 30 to 60 s TTL as `docs/data/15-reporting-data-model.md` already specifies; key `dash:{tenant_id}:{endpoint}:{sha(params)}:{permission_flags}`. Include permission flags in the key so an accountant's cached payload is never served to a dispatcher. Use the existing `dashboard.metrics_stale` event to bump a per-tenant version counter so cache and websocket agree. Heavy aggregates (heatmap, ageing, flow) from materialised views refreshed hourly or nightly (the consumption report already uses a materialised view [R]).
- **Performance.** Aggregate in SQL, never in Python loops; return at most 90 daily points, 10 ranked rows, one matrix; check indexes on `orders.order(created_at, status)`, `orders.order_status_history(to_status, changed_at)`, `accounting.invoice(issued_at, status)`, `complaint.complaint(status, sla_due_at)` (existence not verified; run `EXPLAIN` in the spike). Fix the two capped counts noted in 2.2 item 8 while here.
- **Pagination.** Not needed for ranked widgets (hard `top` limit); any "see all" link goes to the module's own paginated list.
- **RBAC.** All endpoints `reports:read` plus per-section permission, returning `null` for sections the caller cannot see (existing convention).
- **Consistency.** One shared module defines KPI semantics ("delivered" = first `delivered` status change within the IST day, counted once per order) so the dashboard, reports and mobile apps agree; today `delivered_today` uses `COUNT(DISTINCT order_id)` on history, which is a good base.
- **Deprecation.** Once Home no longer reads them, slim `/dashboard/summary` (drop `price_cards`, counts) in a follow-up.
- **New capture (not endpoints):** targets (tenant config keys such as `daily_delivery_target`; none exist in `RECOGNIZED_CONFIG_KEYS` [R]), distributor commission per cylinder and AMDC (for fine impact), trip cost, DBTL/subsidy status. All depend on owner answers.

---

## 10. Accessibility, performance and testing plan

### 10.1 Accessibility (WCAG 2.2 AA, the project standard)

- **Text alternatives.** Each chart has a generated summary in `aria-label` (extend the existing `chartSummary()` idea in `home.ts` with trend and extremes: "Revenue, last 30 days: Rs 8.4 lakh, up 6% on the previous 30 days; highest on 12 Nov") and a "View as table" toggle with the same data.
- **Not colour-only.** Delta chips carry arrow and sign; statuses carry icon and text; high-contrast theme enables decal patterns [W].
- **Contrast.** Chart marks at least 3:1 against the surface in all three themes (WCAG 1.4.11) [S]; text in charts at least 4.5:1.
- **Keyboard.** Legends as `<button>`s; widget menu operable; table fallback is the data path; focus ring tokens already exist (`component.focusRing`).
- **Motion.** No animation under `prefers-reduced-motion`; no auto-moving content longer than 5 s.
- **Live regions.** A single polite `aria-live` region announces attention-queue count changes ("Attention items: 9"), not every data refresh.
- **Audit.** Run Chartability's heuristics once per chart class (bar, line, heatmap, bullet, timeline) [S chartability.fizz.studio] and record results in the feature STATUS.md.

### 10.2 Performance

Targets (proposal, set with the owner): LCP at most 2.5 s on a mid-range laptop and CLS at most 0.1 (Google "good" thresholds [W]); at most 3 API calls on load (overview, attention, one per visible zone batched or streamed); no refetch faster than 60 s except event-driven stale; no widget renders chart code before it is in view. Reserve exact heights for every widget slot; reuse the `SetupChecklist` approach for the one conditional banner. Datasets are tiny (at most 90 points, 168 heatmap cells) so no decimation is needed; avoid canvas-heavy tricks. Replace the leaked-observer pattern with a single shared theme signal service.

### 10.3 Testing

| Layer | What | Tool |
|---|---|---|
| Pure logic | API payload to chart option mappers, KPI delta maths, aria summary text, token resolver, contrast of every chart token in every theme | Jest (already used; mappers are pure and need no canvas) |
| Component | Widget shell states (loading, empty, error, stale), permission gating, table fallback parity with series, reduced-motion flag, dispose on destroy (no leaked observers) | Jest + Angular TestBed with a stubbed chart wrapper; jsdom has no canvas, so assert on the option object and on the SVG renderer output where feasible [U: ECharts server-side SVG rendering mode to be confirmed in the spike] |
| Visual | Every widget in Storybook with Populated / Loading / Empty / Error stories (pattern already used for `StatCard`), captured per theme (light, dark, high-contrast) with animation disabled | Storybook + Playwright screenshots (both installed) |
| Accessibility | Automated axe on Home per role and theme; manual Chartability pass per chart class; keyboard walkthrough | `@axe-core/playwright` (installed; `accessibility.spec.ts` exists) |
| E2E | Role-based Home variants (seed one user per variant), drill-through links land with filters applied, websocket stale event updates one widget without skeleton flicker | Playwright |
| Backend | Unit and integration per endpoint, **tenant-isolation test** (tenant A cannot see tenant B counts), permission nulling, cache key includes permission flags, query plan or timing budget on a seeded large dataset | pytest (existing suite), `mypy --strict`, `import-linter` |
| Performance | Lighthouse CI on Home (LCP, CLS), bundle-size check of the chart chunk | Lighthouse CI, Angular `anyScript` budget |

---

## 11. Phased roadmap, risks and open questions

### 11.1 Roadmap (sizes are relative: S about 2 to 3 days, M about 1 to 2 weeks, L about 3 or more weeks)

| Phase | Scope | Size | Depends on |
|---|---|---|---|
| **P0 Spike and decisions** | Measure ECharts chunk vs Chart.js; wrapper prototype; palette and contrast test; owner answers to Q1 to Q6; check indexes and `EXPLAIN` | S | none |
| **P1 Foundation and MVP** | `@lpg/shared/ui/charts` entry, widget shell, chart tokens (tokens.json, generated CSS/TS/Dart), W01 to W10 using existing data plus endpoints #1, #2, #4; deep-link filters on Orders, Complaints, Invoices, Dispatch; remove obsolete cards; fix CLS and skeleton-flicker; role variants (static); Storybook, a11y and tenant tests | L | P0 |
| **P2 Depth** | W11 to W18, endpoints #3, #5 to #9, global date/comparison/branch controls with URL state, local saved views, role-specific tuning | M to L | P1 |
| **P3 Advanced** | W19 to W23, map provider decision and tiles, constrained widget customisation (CDK drag-drop), server-side saved views, branch comparison | L | P2, Q10 |
| **P4 Intelligence (blocked)** | Anomaly bands, forecasts, narrative digests | L | The owner lifting the AI pause; deterministic stats first |

Process note from AGENTS.md: create `planning/features/<NN>-dashboard-revamp/{PLAN,TASKS,STATUS}.md` before coding, one task at a time; update `planning/current_phase.md` and `knowledge/12-current-status.md` as work lands; record the chart-library choice as a new ADR in `docs/architecture/15-architecture-decision-records.md` (the stack list there names PrimeNG and AG Grid but no chart engine decision was verified).

### 11.2 Risks

| Risk | Impact | Mitigation |
|---|---|---|
| ECharts chunk heavier than estimated | Slower Home | P0 spike, `@defer`, fallback to Chart.js |
| KPI definitions disputed ("delivered", "overdue", "stock cover") | Distrust of the dashboard | One definitions table agreed with the owner, implemented once server-side, shown in tooltips |
| No targets captured | "On track" cannot be asserted | Use baselines (same weekday median of last 4 weeks) and label them as baselines; add targets only after Q1 |
| Aggregations slow at scale under RLS | Home latency | Redis cache, materialised views, `EXPLAIN` in P0, hard result limits |
| Chart accessibility gaps (no keyboard in ECharts) | WCAG 2.2 AA failure | Table fallback, legend buttons, Chartability audit; Highcharts as last-resort swap |
| Colour palette fails in high-contrast/dark | Illegible charts | CI contrast test over tokens, decals in high-contrast |
| Deep-link filters missing on target pages | Click-throughs land unfiltered | Scoped work item in P1, tested in e2e |
| Map tile terms | Blocked or costly maps | Decide provider early in P3, self-host or paid tiles |
| Scope creep into BI | Never-ending dashboard | Ship P1, measure usage, then add |

### 11.3 Open questions for the owner (nothing below is guessed in this report)

1. **Targets.** Does the agency set a daily delivery or revenue target? If not, is "vs same weekday last week" an acceptable baseline?
2. **Definition of "today".** Count a delivery by the day it was delivered, or by the day it was requested? Both can differ across midnight and for rescheduled orders.
3. **Attention ranking.** What does the owner act on first thing in the morning? (Proposed: approvals, past-SLA safety complaints, cash with drivers, stock below reorder.)
4. **OMC numbers.** Which OMC (IOCL, BPCL, HPCL) does each agency use, and which OMC-portal figures should appear in the dashboard? We only hold the platform's own records; there is no OMC portal integration [R, none found].
5. **Fine and margin visibility.** Is distributor commission (AMDC) or per-cylinder margin to be captured? Without it we can show a star rating but not the rupee exposure, and cannot show profitability.
6. **Cost data.** Do agencies want trip cost (fuel, driver pay, vehicle cost)? Not captured today.
7. **Branch scope.** Which roles may compare branches, and do most tenants have more than one branch?
8. **Mobile.** Will the owner and manager use the web Home on a phone, or should a mobile-app dashboard be the main experience? (`docs/ui/06` and `docs/ui/02` disagree.)
9. **AI pause scope.** The owner paused AI automation on 2026-11-19. Does that include the deterministic refill-due heuristic (`refill_heuristic_v1`) that Home already shows? This report assumes not.
10. **Maps.** Is there budget for a map tile provider (OSM community tiles cannot be relied on for commercial production use [W])? Is live fleet visibility wanted on the web at all, given the Driver app already reports location?
11. **Refill-gap rule.** The 25 or 45 day booking-gap norm is reported inconsistently [W]. Confirm with the OMC before any widget flags "early bookings".
12. **Subsidy/DBTL and DAC.** Do agencies want subsidy-credit or DAC-completion tracking on the dashboard? The platform does not hold OMC DAC data today.
13. **Customer privacy.** Which roles may see named top debtors and refill-due customer phone numbers on Home (DPDP exposure)?
14. **Units.** Prefer lakh/crore ("Rs 4.8 L") or thousands separators on dashboard tiles?
15. **History depth.** How many months of order history does a typical tenant have? Heatmaps and baselines need at least 4 to 8 weeks.
16. **Brand colours.** Are `gasBlue` and `flameOrange` fixed for charts, and is it agreed that tenant branding never recolours charts?

---

## 12. Sources

### 12.1 Repository (all `[R]`)

| Path | Used for |
|---|---|
| `AGENTS.md`, `README.md`, `planning/current_phase.md`, `knowledge/01-business-domain.md`, `knowledge/12-current-status.md` | Workflow, stack, roles, KPIs listed as business success metrics |
| `frontend/apps/dashboard/src/app/home/home.ts`, `setup-checklist/setup-checklist.ts` | Current dashboard behaviour and defects |
| `frontend/libs/shared/ui/src/lib/stat-card/*`, `libs/shared/ui/src/data-grid.ts`, `app-shell.ts` | KPI card capabilities; secondary entry-point pattern |
| `frontend/libs/reporting/feature-reports/**`, `libs/reporting/data-access/**` | Existing reports (sales, drivers, GST, consumption, TDT) |
| `frontend/package.json`, `apps/dashboard/project.json`, `frontend/dist/apps/dashboard/browser` | Installed libraries, budgets, measured chunks |
| `design-tokens/tokens.json`, `apps/dashboard/src/styles.css` | Token system, themes, glass rules |
| `docs/ui/02-user-personas.md`, `06-dashboard-layout.md`, `10-color-system.md`, `17-accessibility.md`; `docs/data/15-reporting-data-model.md` | Personas, layout intent, chart palette intent, accessibility, caching plan |
| `docs/research/feature-gap-analysis.md` | Prior domain research (secondary for DAC, PESO, GST and others; I re-verified only TDT, unaccounted-sale and booking-gap) |
| `backend/openapi/openapi.json`, `src/lpg/api/v1/routers/{dashboard,reporting,route,cash_handover,compliance}.py`, `application/dashboard/*`, `infrastructure/persistence/repositories/dashboard.py`, `domain/inventory/inventory_location.py`, `domain/order/order.py`, `domain/tenant/tenant_configuration.py`, `infrastructure/events/realtime_handlers.py`, `migrations/versions/fa52b77ec442_*`, `b3f7c1d9e4a2_*` | Data availability, RBAC, enums, events |

### 12.2 Web, opened and read this session (`[W]`)

| URL | Used for |
|---|---|
| https://www.hindustanpetroleum.com/documents/pdf/10-MDG-2022-01052022.pdf | TDT bands and fines (cl. 4.1 to 4.2), unaccounted sale incl. filled/empty mismatch (cl. 2.1.5). Text extracted and read directly. |
| https://www.angelone.in/news/economy/lpg-booking-gap-increased-to-25-days-from-21-days-government-introduces-new-rule | Booking-gap report and its contradicting editor's note (news, not official) |
| https://ag-grid.com/charts/react/community-vs-enterprise.md and https://www.ag-grid.com/charts/license-pricing/ | AG Charts Community vs Enterprise chart types and licence |
| https://echarts.apache.org/handbook/en/basics/import/ | Tree-shaking imports, renderer choice |
| https://echarts.apache.org/handbook/en/best-practices/aria/ | `aria.show`, label generation, decals; flag-name inconsistency noted |
| https://unpkg.com/ngx-echarts@22.0.0/package.json | Peer deps Angular >=22, echarts >=5 |
| https://unpkg.com/echarts/package.json | echarts 6.1.0, Apache-2.0 |
| https://unpkg.com/ag-charts-angular/package.json | 14.3.0, peer Angular >=20 |
| https://unpkg.com/chart.js/package.json, https://unpkg.com/chartjs-chart-matrix/package.json, https://unpkg.com/chartjs-chart-sankey/package.json | Chart.js 4.6.1, matrix 3.1.0, Sankey 0.19.1 (all MIT) |
| https://www.chartjs.org/docs/latest/general/accessibility.html, https://www.chartjs.org/docs/latest/getting-started/integration.html | Chart.js canvas accessibility, tree-shaking |
| https://tanstack.com/charts/latest/docs/comparison | Gzip size ranges (vendor benchmark; external figures from Bundlephobia snapshots) |
| https://apexcharts.com/license/, https://apexcharts.com/docs/installation/ | ApexCharts licence thresholds and OEM clause; v8 |
| https://shop.highcharts.com/ | Highcharts per-seat prices and licence tiers |
| https://unpkg.com/maplibre-gl/package.json, https://unpkg.com/leaflet/package.json, https://unpkg.com/gridstack/package.json, https://unpkg.com/@swimlane/ngx-charts/package.json | Versions and licences |
| https://operations.osmfoundation.org/policies/tiles/ | OSM tile usage policy |
| https://carbondesignsystem.com/data-visualization/color-palettes/, https://carbondesignsystem.com/data-visualization/dashboards/ | Palette types, dark-theme handling, dashboard hierarchy |
| https://learn.microsoft.com/en-us/power-bi/create-reports/service-reports-visual-interactions | Cross-filter, cross-highlight, drilling |
| https://grafana.com/docs/grafana/latest/visualizations/dashboards/build-dashboards/best-practices/ | Audience-scoped dashboards, refresh guidance, stacking caution |
| https://web.dev/articles/cls | CLS thresholds and causes |

### 12.3 Web, search-result summaries only (`[S]`, not opened)

| URL | Used for |
|---|---|
| https://chartability.fizz.studio/ | Chartability accessibility heuristics |
| https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast | 3:1 for graphical objects |
| https://www.datawrapper.de/blog/dual-axis-charts-guide and https://www.datawrapper.de/academy/what-to-consider-when-creating-a-pie-chart | Dual-axis and pie guidance |
| https://www.perceptualedge.com/blog/?p=217 and https://www.telerik.com/docs/default-source/blogs-docs/bullet_graph_design_spec-pdf | Bullet graph specification |
| https://help.tableau.com/current/online/en-us/pulse_insights_platform_insight_types.htm | Tableau Pulse: statistics first, language on top |
| https://support.stripe.com/questions/customize-your-dashboard-home-page-charts-for-better-business-insights | Stripe Home: comparison range, add/remove/reorder widgets |
| https://linear.app/docs/insights | Linear Insights: flexible, shareable dashboards |
| https://www.think.design/blog/dashboard-design-in-2026-dos-and-donts/, https://dashtemplate.com/blog/dashboard-best-practices-2026/, https://www.uxpin.com/studio/blog/dashboard-design-principles/, https://improvado.io/blog/dashboard-design-guide, https://www.boundev.ai/blog/dashboard-design-best-practices-guide | Answers-first, KPI context, metric limits (vendor blogs) |
| https://www.cursa.app/en/page/analytics-dashboards-for-logistics-kpis-visual-design-and-decision-cadences, https://fleetrabbit.com/industry/transportation-and-logistics/trucking-fleet-kpi-dashboard-every-operations-director-should-track-2026 | Logistics heatmaps and on-time KPI practice (vendor content) |
| https://busy.in/gst-rates/lpg-cylinder/ | GST on domestic vs commercial LPG (sources disagree on edge cases) |
| https://ianslive.in/delivery-authentication-code-based-gas-deliveries-reach-over-945-pc-to-prevent-diversion-govt--20260425182140 | DAC adoption (news report) |
| Okabe-Ito and Paul Tol palettes via https://cran.r-project.org/web/packages/khroma/readme/README.html and https://conceptviz.app/blog/okabe-ito-palette-hex-codes-complete-reference | Palette hex values; use original papers (Okabe and Ito 2008, Wong 2011, Tol SRON/EPS/TN/09-002) for a formal citation |

### 12.4 Not verified (`[U]`) and gaps

- Dribbble, Behance and Mobbin galleries and first-party Stripe, Vercel and Shopify dashboard design write-ups were **not opened**; no claim above rests on them.
- ECharts' tree-shaken bundle size for our module set, Leaflet and MapLibre bundle sizes, and `Intl` compact notation output for `en-IN` ("L", "Cr") need a measurement or browser check.
- ECharts keyboard navigation is not documented on the accessibility page I read; I treat it as absent.
- ECharts server-side SVG rendering for Jest tests is from memory; confirm in the spike.
- WCAG 2.2 SC 2.5.8 (target size 24 px) and the Angular `anyScript` budget type are cited from general knowledge, not re-fetched.
- I did not run the app, so layout shift, skeleton flicker and the observer leak are code-reading findings, not measurements.
- Index existence for the suggested aggregation queries was not checked.
- DAC code length and PESO licence timings come from the prior repo research doc and its cited sources; I did not re-open them.
