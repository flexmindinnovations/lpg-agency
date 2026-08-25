"""Change Employee Status Use Case.

Covers activate / put-on-leave / deactivate — one command, since they're all
the same domain operation (`Employee.change_status`), just with different
target values. The frontend's "Deactivate" action is this with
`new_status="inactive"`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.errors import NotFoundError

if TYPE_CHECKING:
    import uuid

    from lpg.application.tenant_admin.ports import EmployeeRepository
    from lpg.domain.tenant_admin.employee import Employee


@dataclass(frozen=True, slots=True)
class ChangeEmployeeStatusCommand:
    employee_id: uuid.UUID
    new_status: str


class ChangeEmployeeStatusUseCase:
    def __init__(self, employee_repo: EmployeeRepository) -> None:
        self._employee_repo = employee_repo

    async def execute(self, cmd: ChangeEmployeeStatusCommand) -> Employee:
        employee = await self._employee_repo.get_by_id(cmd.employee_id)
        if employee is None:
            msg = f"Employee '{cmd.employee_id}' was not found."
            raise NotFoundError(msg)

        employee.change_status(cmd.new_status)

        await self._employee_repo.save(employee)
        return employee
