# QA fixes — dashboard-wide UI/UX (engineer: ui)

Branch `qa-fix/ui`. Scope: shared components (`libs/shared/*`), the app shell,
and surgical edits in feature templates.

## Shared date format (DA-31, DO-08) — for other engineers

Use `@lpg/shared/util` everywhere a date is shown or typed:

- `formatDisplayDate(v)` → "20 Oct 2026"; `formatDisplayDateTime(v)` → "20 Oct 2026, 10:09" (24-hour, IST).
  Date-only API strings ("2026-10-20") are never shifted by a time-zone conversion.
- Pipes `LpgDatePipe` (`| lpgDate`) and `LpgDateTimePipe` (`| lpgDateTime`) for templates.
- `toIsoDate(date)` → "2026-10-20" for API `date` fields (no UTC shift of a picked day).
- `parseDisplayDate('15/06/1985')`, `DATE_INPUT_FORMAT` ('dd/mm/yy'), `DATE_INPUT_PLACEHOLDER` ('dd/mm/yyyy').
- Every `p-datepicker` now reads dd/mm/yyyy by default (PrimeNG `translation.dateFormat` in
  `app.config.ts`) — do not set `dateFormat` on a datepicker.
- `@lpg/shared/ui`'s `formatReportDate` / `formatTimestamp` now delegate to these.

## Findings

| Finding | What changed | Files | Verified |
|---|---|---|---|
| UR-01 (+DO-25 clipping) | PrimeNG `overlayAppendTo: 'body'` app-wide: every select/date/autocomplete/multiselect panel opens on `<body>`, never clipped by a drawer/dialog body. `DrawerA11yDirective` pins each drawer itself inline (its inert/focus contract needs that) and names the drawer close button. | `apps/dashboard/src/app/app.config.ts`, `libs/shared/ui/.../drawer-a11y.directive.ts` | unit tests; Playwright (below) |
| DO-08 / DA-31 | Shared date util (above); PrimeNG `translation.dateFormat = 'dd/mm/yy'`; per-picker `dateFormat` overrides removed (dispatch, drivers, vehicles, scales, cylinder units, orders, platform flags, compliance panel); invoices list/drawer use it; shared `formatReportDate`/`formatTimestamp` delegate. | `libs/shared/util/src/lib/date-format.ts` (+spec) | jest |
| DO-21 | `AppMessageService` (provided as `MessageService`): a success clears stale toasts, one lifetime per severity. Toasts top-centre below the header with `preventDuplicates` (never over drawer footers or the close button). Complaints page no longer provides its own `MessageService` (its toasts were going nowhere). | `libs/shared/data-access/src/lib/services/app-message.service.ts` (+spec), `shell-layout.ts`, `platform-shell.ts`, `styles.css`, `feature-complaints.ts` | jest |
| DA-22 / DA-23 chips | Per-theme `--component-chip-*` tokens (light/dark/system-dark/high-contrast, all ≥6.4:1) drive `p-tag` via the preset and the activity list. Root cause: Aura's `light-dark()` chip colours followed AG Grid's `color-scheme: light`. Hardcoded danger-tag hex removed. | `tokens.css`, `primeng-preset.ts`, `activity-list.component.ts`, `styles.css` | contrast script; axe |
| DA-20 / DO-36 | Phone (<768px): sidebar is an off-canvas menu behind a header hamburger, closed by default, `inert` while closed, closes on navigation/Escape/backdrop, full-width content. Tablet (<1200px): starts as icon rail, tighter gutters. | `libs/shared/ui/.../app-shell.component.ts` (+spec) | jest; Playwright 390/820 |
| DA-21 | Grid columns get a readable `minWidth` (grid scrolls sideways instead of truncating), optional `priority: 'low'` columns hide under 720px; toolbar buttons never break mid-label. | `data-grid.component.ts` (+spec), `styles.css` | jest |
| UR-02 / UR-03 | Page title + subtitle single-line with ellipsis (global `.page-title/.page-subtitle` and `lpg-page-header`), header spacer can shrink. All subtitles in the UR-03 table replaced; "tenant"/"registry"/"historized" wording removed from Compliance Calendar ("Agency insurance"), TDT config, feature flags, cylinder units, TDT report empty state. Compliance panel heading made optional so the calendar no longer repeats "Compliance Documents". Sidebar header divider so scrolled items don't sit under the logo; active item kept in view. | feature templates (text only), `compliance-documents-panel.*` | visual |
| DA-23 / DO-35 (shell) | Nav group labels at full secondary colour (4.6:1 light / 5.2:1 dark); breadcrumb Home `homeAriaLabel="Home"`; drawer close buttons named; header Search button text contrast (surface-base fill). | app-shell, drawer-a11y, shell-layout | axe |
| DA-15 | `lpg-data-grid` `[error]` + `(retry)`: error state with Retry instead of an empty grid; designed empty text instead of "No Rows To Show". Wired: Branches, Users, Warehouses, Cylinder Types, Pricing, Invoices, Customers (toast replaced), Audit Log. Reports root cause: the store read `error.message`, which the normalised `AppError` lacks → `undefined` → empty report; now `loadErrorMessage()`. | `data-grid.component.ts`, `reporting.store.ts` (+spec), the pages | jest |
| UR-04 / DA-25 | Backend: `audit_labels.py` names every audited record (order/invoice/complaint/GRN numbers, registration, "Name (CN-…)", "Trip on 20 Oct 2026 · KA01AB1234", child rows → parent's number). Written at flush time from already-loaded objects (no query); older/unlabelled rows labelled at read time from stored state + one RLS-scoped query per parent table. API: `action`, `date_from`, `date_to` filters, bounded `limit`, new `GET /admin/audit-log/entity-types`. Frontend: When / Record / Record type / Action / Done by, filters (type, action, person, dates), search, "What changed" table, CSV export, ids only in the drawer, copy-ID cell is a named non-clipping button. | backend `audit.py`, `audit_labels.py`, `repositories/audit.py`, `application/audit/*`, `routers/admin.py`; frontend `feature-audit-log`, `admin-audit-log.service.ts`, `activity-cells.ts` | unit `test_audit_labels.py`; integration `test_audit_log_repository.py` (labels, cross-tenant parent never read, action filter, entity types) |
