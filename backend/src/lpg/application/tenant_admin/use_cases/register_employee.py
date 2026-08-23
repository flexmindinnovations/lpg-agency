"""Register Employee Use Case.

Registers a new employee within the tenant, creating an Employee aggregate.
The registration triggers a domain event (EmployeeRegistered) which
will asynchronously provision the IdentityUser and other role-specific
projections (like Driver).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.errors import ApplicationError
from lpg.domain.tenant_admin.employee import Employee

if TYPE_CHECKING:
    import uuid

    from lpg.application.common.ports import TenantContext, UnitOfWork
    from lpg.application.tenant_admin.ports import EmployeeRepository


@dataclass(frozen=True, slots=True)
class RegisterEmployeeCommand:
    tenant_id: uuid.UUID
    branch_id: uuid.UUID
    first_name: str
    last_name: str
    phone_number: str
    role: str
    email: str | None = None


class RegisterEmployeeUseCase:
    """Registers a new employee in the tenant context."""

    def __init__(
        self,
        tenant_context: TenantContext,
        uow: UnitOfWork,
        employee_repo: EmployeeRepository,
    ) -> None:
        self._tenant_context = tenant_context
        self._uow = uow
        self._employee_repo = employee_repo

    async def execute(self, cmd: RegisterEmployeeCommand) -> uuid.UUID:
        # Verify tenant scope
        if cmd.tenant_id != self._tenant_context.tenant_id:
            msg = "Cross-tenant employee registration is forbidden."
            raise ApplicationError(msg)

        # `self._uow` arrives already entered by `get_unit_of_work`'s own
        # `async with uow: yield uow`, which spans the whole request and
        # commits exactly once, on that outer exit — after the router has
        # had a chance to read back what this method just saved, in the
        # same transaction. Opening a *second*, nested `async with
        # self._uow:` here used to commit early on this method's own return,
        # which — since the RLS tenant context is set transaction-scoped
        # (`set_config(..., is_local => true)`, cleared on commit) — made
        # the router's post-registration `repository.get_by_id()` reload run
        # with no tenant context and see nothing. Not opening one here
        # matches every other use case built against this same raw,
        # router-owned `UnitOfWork` (e.g. `InviteStaffUserUseCase`).
        employee_id = self._employee_repo.next_id()
        employee_code = await self._employee_repo.next_employee_code(cmd.tenant_id)

        employee = Employee(
            employee_id=employee_id,
            tenant_id=cmd.tenant_id,
            branch_id=cmd.branch_id,
            employee_code=employee_code,
            first_name=cmd.first_name,
            last_name=cmd.last_name,
            phone_number=cmd.phone_number,
            email=cmd.email,
            role=cmd.role,
        )

        await self._employee_repo.save(employee)

        # Domain events are dispatched by the UnitOfWork on commit —
        # EmployeeRegistered will trigger IdentityUser creation.
        return employee.id
