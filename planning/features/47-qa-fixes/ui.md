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
| DA-29 | One validation pattern: `lpg-form-field` shows a field's message when it is touched **or** its form is submitted, and wires `aria-invalid` / `aria-describedby`; `validateForSubmit(form)` marks everything touched and returns validity. Submit buttons stay enabled (removed `form.invalid ||` from `[disabled]` on 23 submit buttons) so a click explains what is missing instead of doing nothing. | `form-field.component.ts` (+spec), admin pages, platform agencies, employees, drivers, vehicles, scales, cylinder units, compliance panel | jest |
| DA-27 | The "Invalid PrimeUI License" badge is PrimeUI's own licence check (closed shadow root) — not hidden. It shows in dev because no local `PRIME_NG_LICENSE_KEY` is set; toasts moved top-centre so it no longer covers them. Production: `deploy.yml` now fails the web image build when the key secret is empty instead of shipping the badge. | `.github/workflows/deploy.yml` | workflow review |
| DA-23 (Home) | Both Home charts carry a text alternative with the same numbers ("Fleet status: 4 available, 1 in maintenance."); chart labels readable ("In maintenance" not `in_maintenance`); Recent Activity rows show the record name and Created/Changed/Deleted instead of an id fragment; refill due dates in the app format. | `apps/dashboard/src/app/home/home.ts` | jest, build |
| DO-35 (dispatch) | New-trip Branch picker named (`ariaLabel`). | `feature-dispatch.html` (one attribute) | lint |

## Deferred

- **Full axe re-run (light + dark) on key pages** — not re-run after the final commits for time; the
  lead's integrated QA pass on the merged branch should run `@axe-core/playwright` over Home, Orders,
  Dispatch, Audit Log, Customers in both themes. Known-remaining candidates: `#trip_spare_*`
  `aria-valid-attr-value` (PrimeNG `p-inputnumber` writes `aria-valuemax` without a max), Cylinder
  Units Quick Scan input label, design-system `#ds-role` select label, high-contrast avatar initial,
  "No trips." hint contrast.
- **DO-25 Branch select height / Register Employee role list at 820px** — overlay clipping is fixed
  globally; the collapsed-select height was not re-checked visually.
- **Forms in Inventory, Complaints, Orders, Dispatch** keep `[disabled]="form.invalid"` — those screens
  are being rewritten by other engineers; they should adopt `validateForSubmit` + `lpg-form-field`.
- **"Done by" shows the user's e-mail** — identity users have no stored display name; real names need
  an identity-model change.
- **Dev licence badge** — needs a local `PRIME_NG_LICENSE_KEY`; nothing to do in code.
- **Empty states / loading skeletons sweep** — grids got designed empty/error states; a per-page
  skeleton sweep was not done.
- **Initial bundle** is 717 kB vs the 700 kB warning budget (warning only, below the 1 MB error).

## Migrations / API

- No Alembic migration.
- API: `GET /admin/audit-log` gains `action`, `date_from`, `date_to`, bounded `limit` (1–200),
  `entity_name` max length 100; new `GET /admin/audit-log/entity-types`. OpenAPI and client
  regenerated in `chore(api): regenerate client` (also picked up pre-existing route-stop
  `order_number` drift).

## ADR draft

**Dashboard-wide UI conventions (proposed amendment to ADR-028).**
1. PrimeNG overlays append to `<body>` app-wide (`overlayAppendTo`); drawers stay inline via
   `DrawerA11yDirective` because their inert/focus handling depends on DOM position.
2. One date format: "20 Oct 2026" / "20 Oct 2026, 10:09", Asia/Kolkata, dd/mm/yyyy inputs — only via
   `@lpg/shared/util` (`formatDisplayDate`, `formatDisplayDateTime`, `lpgDate`, `lpgDateTime`).
3. One toast behaviour: `AppMessageService` (top-centre, success clears stale errors, lifetime per
   severity); features never provide their own `MessageService`.
4. One validation pattern: submit enabled, messages on touch or submit via `lpg-form-field`.
5. Status chips colour only from `--component-chip-*` tokens, per theme.
6. List pages show failures through `lpg-data-grid`'s `[error]`/`(retry)`, never an empty grid.
