# Phase 16: Employees (Tenant Admin) Implementation Plan

## Goal
Give a tenant a single, centralized HR record per staff member (`Employee`) — the record `Driver` and other role-specific aggregates reference by `employee_id`, and the thing an `agency_admin` registers before a staff account can do anything role-specific.

## Scope
1. **Domain Layer**: `Employee` aggregate root (`domain/tenant_admin/employee.py`) — code/name/phone validation, `active`/`on_leave`/`inactive` status with `inactive` as a one-way terminal state.
2. **Application Layer**: `RegisterEmployeeUseCase`, `ListEmployeesUseCase`.
3. **Infrastructure Layer**: `SqlAlchemyEmployeeRepository`, `tenant.employee` table + `tenant.employee_code_seq` (auto-generated `EMP####` codes).
4. **API Layer**: `POST /employees` (`users:manage`, `agency_admin` only), `GET /employees` (`users:read`, broader staff roles).
5. **Frontend UI**: `@lpg/employee/feature-employees`.

## Explicitly NOT this phase
`application/identity/staff_user.py` (`InviteStaffUserUseCase`,
`DeactivateStaffUserUseCase`, `ReassignRoleUseCase`, permission management —
exposed via the `admin` router) operates on the `IdentityUser` aggregate:
login credentials and RBAC. `Employee` is the HR record; `IdentityUser` is
the account. `EmployeeRegistered` is documented (`docs/data/09-domain-events.md`)
as the trigger for provisioning the matching `IdentityUser`/`Driver`
projections, but no handler subscribes to it yet — the two are registered
independently through separate endpoints today, not chained.

## Integration points
- `delivery.driver.employee_id` FKs to this table — a `Driver` cannot exist
  without a matching `Employee` row.
- Publishes `EmployeeRegistered`/`EmployeeStatusChanged`; no subscriber
  exists yet (see the note above).

## Out of Scope
- Automatic `IdentityUser`/`Driver` provisioning from `EmployeeRegistered`.
- Employee profile editing (name/phone/branch change) — only status
  transitions exist beyond registration.
