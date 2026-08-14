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
        pass

        # Verify tenant scope
        if cmd.tenant_id != self._tenant_context.tenant_id:
            msg = "Cross-tenant employee registration is forbidden."
            raise ApplicationError(msg)

        async with self._uow:
            # Generate ID and employee code inside the transaction
            employee_id = self._employee_repo.next_id()
            employee_code = await self._employee_repo.next_employee_code()

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

            # Domain events are dispatched by the UnitOfWork on exit
            # EmployeeRegistered will trigger IdentityUser creation
            return employee.id
