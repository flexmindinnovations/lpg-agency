# Phase 16: Employees (Tenant Admin) Status

> Backfilled 2026-08-19 (R8). No PLAN/TASKS/STATUS ever existed for this
> phase before — it shipped, then C4 (`planning/MODULE_STATUS.md`) found it
> had zero test coverage. This is precisely the table C4 called out by
> name: "the table whose missing GRANT caused a production-shaped outage
> that no test caught" (a defect from an earlier phase, independently
> hardened by migration `b4d19e7c3a52`). R7 then added the coverage this
> file documents.

## Current Status
- **State:** ✅ **COMPLETE** — backend implemented, tested, and verified. Frontend implemented but not live-browser-verified in this pass.
- **Test coverage added:** 2026-08-19 (R7)

## Backend — ✅ complete and independently verified

- [x] Domain model (`Employee` aggregate, status transition table, constructor validation)
- [x] Application use cases (register, list)
- [x] Repository implementation
- [x] Alembic migrations (`ca542bd9a61e`, `b4d19e7c3a52`)
- [x] REST API (`POST /employees`, `GET /employees`)
- [x] Gates: ruff, mypy, all 5 import-linter contracts, full unit + integration suites green
- [x] Domain unit tests (`test_domain_employee.py`), use-case unit tests (`test_employee_use_cases.py`), through-the-stack integration + RBAC tests (`test_employee_endpoints_smoke.py`, `test_employee_rbac.py`)

### Two independent real bugs found and fixed while adding test coverage (R7, 2026-08-19)

Zero tests existed before R7. Both bugs below produced the *identical*
symptom (`assert employee is not None` crashing every real registration),
which is exactly why a second, independent root cause survived undetected
even once the first was found — only an actual end-to-end test against a
real database would have caught either.

1. **Premature commit wiped the RLS tenant context.** `RegisterEmployeeUseCase`
   wrapped its body in a *second*, nested `async with self._uow:`, even
   though the raw `UnitOfWork` it receives is already entered by
   `get_unit_of_work`'s own request-spanning context manager. That nested
   block's own exit committed early — and since the RLS tenant context is
   transaction-scoped (`set_config(..., is_local => true)`, cleared on
   commit) — the router's post-registration `repository.get_by_id()` reload
   ran with no tenant context and saw nothing. Fixed by removing the nested
   `async with`, matching every other use case built against a raw,
   router-owned `UnitOfWork` (e.g. `InviteStaffUserUseCase`).
2. **Missing flush, same symptom, different cause.**
   `SqlAlchemyEmployeeRepository.save()` never flushed after
   `session.add(row)` on the insert path. The session factory disables
   autoflush project-wide, so even after fix #1, the reload still saw
   nothing. Fixed by adding `await self._uow.session.flush()`, matching
   every other repository's `save()` (inventory, order, route,
   cylinder_ledger).

## Frontend — 🟡 implemented, not re-verified this pass

- [x] Nx library scaffolded (`@lpg/employee/feature-employees`)
- [x] Wired into `app.routes.ts`
- [ ] Not live-browser-verified in this session (R7 was a backend-only pass)

## Completion Notes

1. `RegisterEmployeeUseCase.execute()` also had a stray, no-op `pass`
   statement at its top (dead code, harmless, noted but not removed as part
   of the R7 fix since it doesn't change behavior).
2. `Employee.__init__` — not just `.create()` — records `EmployeeRegistered`
   on every construction, including rehydration from the database. The
   repository's `_to_domain()` immediately calls `employee.clear_events()`
   to discard that spurious rehydration-time event before it could ever be
   dispatched; only the genuinely-new registration's event survives.
