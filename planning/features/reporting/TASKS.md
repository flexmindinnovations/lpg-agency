# Phase: Reporting Tasks

> Backfilled 2026-08-19 (R8) — the feature shipped without this file ever
> being created; the checklist below reflects what was actually built,
> reconstructed from the code and from R7a/R7's fix history.

- [x] 1. Implement Application Layer query use cases (`GetDailySalesUseCase`, `GetGstReportUseCase`, `GetDriverPerformanceUseCase`, `GetCustomerConsumptionUseCase`)
- [x] 2. Implement Infrastructure Layer (`SqlAlchemyReportingRepository`, raw SQL against `rpt.*` views — no ORM models)
- [x] 3. Generate Alembic migration (`bab6ab8f401f`) — `rpt` schema, 2 plain views, 3 materialized views, unique indexes for concurrent refresh, grants
- [x] 4. Grant `reports:read` permission (`b3f7c1d9e4a2`) to staff-facing roles
- [x] 5. Implement API Layer (`routers/reporting.py`)
- [x] 6. Implement nightly materialized-view refresh (`infrastructure/jobs/refresh_views.py`, ARQ cron job, 2:00 AM)
- [x] 7. Implement Frontend (`@lpg/reporting/feature-reports`, `ReportingStore`)
- [x] 8. Wire `/reports` route into dashboard `app.routes.ts`
- [x] 9. (R7a, 2026-08-19) **Fix: mount the router.** `api/app.py` imported `reporting` but never called `app.include_router(reporting.router, ...)` — all four endpoints 404'd unconditionally since the module was first built. Found by a documentation audit, not by any test (there were none). Added the missing line plus a smoke-test file.
- [x] 10. (R7, 2026-08-19) Extend test coverage with real seeded data + explicit `REFRESH MATERIALIZED VIEW` for `/gst`, `/drivers`, `/consumption` (R7a's own tests only proved `/sales`, the one plain view, against real data)
- [x] 11. (R8, 2026-08-19) Backfill this planning directory
