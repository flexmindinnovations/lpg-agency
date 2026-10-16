"""Enable Driver Login Use Case.

Gives a driver employee the phone login the Driver App signs in with. Staff
roles are not handled here: they sign in to the dashboard with an email and
password, which Users & Roles manages.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.errors import (
    ApplicationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)

if TYPE_CHECKING:
    import uuid

    from lpg.application.common.ports import TenantContext
    from lpg.application.tenant_admin.ports import (
        DriverLoginProvisioner,
        DriverLoginResult,
        EmployeeRepository,
    )


@dataclass(frozen=True, slots=True)
class EnableDriverLoginCommand:
    tenant_id: uuid.UUID
    employee_id: uuid.UUID


class EnableDriverLoginUseCase:
    def __init__(
        self,
        tenant_context: TenantContext,
        employee_repo: EmployeeRepository,
        provisioner: DriverLoginProvisioner,
    ) -> None:
        self._tenant_context = tenant_context
        self._employee_repo = employee_repo
        self._provisioner = provisioner

    async def execute(self, cmd: EnableDriverLoginCommand) -> DriverLoginResult:
        if cmd.tenant_id != self._tenant_context.tenant_id:
            msg = "Cross-tenant login provisioning is forbidden."
            raise ApplicationError(msg)

        employee = await self._employee_repo.get_by_id(cmd.employee_id)
        if employee is None:
            msg = f"No employee visible with id {cmd.employee_id}."
            raise NotFoundError(msg, employee_id=str(cmd.employee_id))
        if employee.role != "driver":
            msg = (
                "Only driver employees get a Driver App login; staff sign in to the "
                "dashboard (manage them under Users & Roles)."
            )
            raise ValidationError(msg)
        if employee.status != "active":
            msg = "Only an active employee can be given a login."
            raise ConflictError(msg, employee_id=str(cmd.employee_id))

        return await self._provisioner.enable(cmd.tenant_id, employee)
