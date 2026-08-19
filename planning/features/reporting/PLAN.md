# Phase: Reporting Implementation Plan

> No phase number was ever assigned to this module — `planning/MODULE_STATUS.md`'s
> own summary table lists it as "folded into 18" (Printing Engine) with a
> `—` in the phase column. This directory is named `reporting`, not
> `NN-reporting`, to match that.

## Goal
Give staff read-only aggregate views over data that already exists elsewhere (invoices, deliveries, cylinder exchanges) — daily sales, GST filing totals, driver performance, customer consumption — without adding a new domain or duplicating data ownership.

## Scope
1. **No domain layer.** Pure CQRS over SQL read models — there is no aggregate to protect an invariant on; the source of truth is `accounting.invoice`, `delivery.route`/`route_stop`, and `cylinder_ledger.ledger_transaction`.
2. **Application Layer**: four thin query use cases (`GetDailySalesUseCase`, `GetGstReportUseCase`, `GetDriverPerformanceUseCase`, `GetCustomerConsumptionUseCase`) — each a pass-through to the repository.
3. **Infrastructure Layer**: `SqlAlchemyReportingRepository` — every method is a raw `sa.text()` `SELECT` against the `rpt` schema's views; no ORM models.
4. **Database**: `rpt` schema — `vw_daily_sales`/`vw_outstanding_balances` as plain views (reflect new rows immediately), `mv_gst_filing_period`/`mv_customer_consumption`/`mv_driver_performance_daily` as materialized views (refreshed nightly by `refresh_materialized_views`, an ARQ cron job).
5. **API Layer**: `GET /reporting/sales`, `/gst`, `/drivers`, `/consumption`.
6. **Frontend UI**: `@lpg/reporting/feature-reports`, backed by `ReportingStore` (`@ngrx/signals`) calling the endpoints directly via `HttpClient` rather than the generated OpenAPI client.

## Integration points
- Nightly refresh (2:00 AM) via `infrastructure/jobs/refresh_views.py`, registered in `WorkerSettings.cron_jobs`; each materialized view refreshes independently — one view's failure doesn't block the others.
- `reports:read` permission — granted to staff-facing roles only (`super_admin`, `agency_admin`, `manager`, `warehouse_staff`, `dispatcher`, `accountant`); deliberately **not** `driver`/`customer`, who use the mobile apps instead.

## Out of Scope
- `get_outstanding_balances` exists on the repository/port but has no query
  use case or endpoint — a dead port method, not a shipped report.
- Ad-hoc/custom report building — the four reports are fixed shapes.
- Real-time refresh of the three materialized views (nightly only; a manual
  `REFRESH MATERIALIZED VIEW` is the only way to see same-day data sooner).
