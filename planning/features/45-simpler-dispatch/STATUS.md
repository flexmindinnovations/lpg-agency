# 45 — Simpler dispatch (trip sheet) — Status

**2026-10-19 — Done.** Backend ruff, ruff format, mypy --strict, import-linter,
OpenAPI drift check and the unit suite pass; the route, order, inventory, cash
and payment integration suites pass against a local PostgreSQL + Redis + moto.
Frontend prettier, lint, test and build pass. Tried live on a local dashboard:
New trip → three orders → Load & dispatch moved the trip to Ready to leave.
No Driver App change and no migration.

**2026-10-19 — Order page Send out added.** A confirmed order goes out from its
own page: Send out picks a new trip's driver and van (busy ones disabled) or an
open trip, plus the godown, shows the cylinders against van and godown stock,
and calls plan + load-and-dispatch. A progress line shows Booked → Confirmed →
On a trip → Out for delivery → Delivered with the trip's driver and van. Lint,
test and build pass; tried live on a local dashboard (confirmed order joined an
open trip and moved to Ready For Dispatch). The e2e workflow now uses Send out.
