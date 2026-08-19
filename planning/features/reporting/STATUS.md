# Phase: Reporting Status

> Backfilled 2026-08-19 (R8). No PLAN/TASKS/STATUS ever existed for this
> module before — it shipped ~90% built and was then found, by a
> documentation audit rather than any test, to be **100% unreachable**: the
> router was imported but never mounted. R7a fixed the mount; R7 then
> extended test coverage to the three materialized-view-backed reports.
> This file documents the real, current, verified state.

## Current Status
- **State:** ✅ **COMPLETE** — backend implemented, mounted, and fully tested. Frontend implemented but not live-browser-verified in this pass.
- **Router mount fixed:** 2026-08-19 (R7a)
- **Full test coverage added:** 2026-08-19 (R7a, R7)

## Backend — ✅ complete and independently verified

- [x] Application query use cases (4)
- [x] Repository implementation (raw SQL against `rpt.*` views)
- [x] Alembic migrations (`bab6ab8f401f` schema/views, `b3f7c1d9e4a2` permission grant)
- [x] REST API (`GET /reporting/sales`, `/gst`, `/drivers`, `/consumption`)
- [x] Nightly materialized-view refresh (ARQ cron, 2:00 AM), per-view failure isolation
- [x] Gates: ruff, mypy, all 5 import-linter contracts, full unit + integration suites green
- [x] Integration tests: mount/reachability, RBAC allow/deny, tenant-scoping against real seeded data for all four endpoints — including real-data assertions against all three materialized views (post-`REFRESH`), not just the one plain view

### The defect this module is the cautionary tale for (C7, fixed R7a, 2026-08-19)

`api/app.py` imported the `reporting` router module alongside every other
router, but the corresponding `app.include_router(reporting.router, ...)`
line simply did not exist — 16 `include_router` calls, and reporting was
never one of them. The module was dead code end to end:

- All four endpoints 404'd unconditionally.
- The frontend (`ReportingStore`) already called the correct paths and
  simply failed every time.
- `docs/data/11-api-contracts.md` separately documented these under
  `/api/v1/reports/...` (plural) while the code used `/reporting/...` — the
  contract doc wouldn't have matched even once mounted. Corrected.

No test caught this because there were no tests for this module at all
(C4) — ruff didn't flag the unused import either, since the module name
*was* referenced in the import list, just never passed to
`include_router()`. Fixed with a one-line router mount plus a new smoke
test file proving reachability, RBAC, and real-data correctness.

## Frontend — 🟡 implemented, not re-verified this pass

- [x] Nx library scaffolded (`@lpg/reporting/feature-reports`)
- [x] `ReportingStore` (`@ngrx/signals`) — calls the four endpoints directly
      via `HttpClient`, not through the generated OpenAPI client
- [x] Wired into `app.routes.ts`
- [ ] Not live-browser-verified in this session (R7a/R7 were backend-only
      passes; the frontend was already calling the right URLs and needed no
      code change once the backend mount was fixed)

## Completion Notes

1. `get_outstanding_balances` exists on `ReportingRepository`/
   `SqlAlchemyReportingRepository` with no query use case or API endpoint
   ever built around it — a dead port method, left as-is (not this
   backfill's job to either wire it up or remove it).
2. The three materialized views are **not** auto-refreshing — data seeded
   same-day won't appear in `/gst`, `/drivers`, or `/consumption` until the
   nightly 2:00 AM job runs, or someone issues a manual
   `REFRESH MATERIALIZED VIEW`. `/sales` (a plain view) has no such lag.
3. `reports:read` is deliberately not granted to `driver`/`customer` — they
   use the mobile apps, not this staff-facing surface.
