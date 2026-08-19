# Phase 16: Employees (Tenant Admin) Tasks

> Backfilled 2026-08-19 (R8) — the feature shipped without this file ever
> being created; the checklist below reflects what was actually built,
> reconstructed from the code and from R7's fix history.

- [x] 1. Implement Domain Layer (`backend/src/lpg/domain/tenant_admin/employee.py`) — `Employee` aggregate, `EMPLOYEE_STATUSES` transition table, `EmployeeRegistered`/`EmployeeStatusChanged` events
- [x] 2. Implement Application Layer Use Cases (`RegisterEmployeeUseCase`, `ListEmployeesUseCase`)
- [x] 3. Implement Infrastructure Layer (`SqlAlchemyEmployeeRepository`, `EmployeeModel` in `models/tenant.py`, `tenant.employee_code_seq`)
- [x] 4. Generate Alembic migrations (`ca542bd9a61e` centralized employee table + code sequence + driver FK migration, `b4d19e7c3a52` hardened grants and RLS)
- [x] 5. Implement API Layer (`routers/employee.py`, `users:manage`/`users:read` permission codes)
- [x] 6. Implement Frontend (`@lpg/employee/feature-employees` library)
- [x] 7. Wire `/employees` route into dashboard `app.routes.ts`
- [x] 8. (R7, 2026-08-19) Add domain/use-case/integration test coverage — zero existed before; found and fixed 2 independent real backend bugs that both crashed *every real employee registration* (a premature-commit-clears-RLS-context bug, then a missing-flush bug with the identical symptom)
- [x] 9. (R8, 2026-08-19) Backfill this planning directory
