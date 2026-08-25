"""Update Employee Use Case.

Updates an existing employee's editable HR fields (name, phone, email, role,
branch). Deliberately excludes `status` — see `ChangeEmployeeStatusUseCase`.
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
class UpdateEmployeeCommand:
    employee_id: uuid.UUID
    branch_id: uuid.UUID
    first_name: str
    last_name: str
    phone_number: str
    role: str
    email: str | None = None


class UpdateEmployeeUseCase:
    def __init__(self, employee_repo: EmployeeRepository) -> None:
        self._employee_repo = employee_repo

    async def execute(self, cmd: UpdateEmployeeCommand) -> Employee:
        employee = await self._employee_repo.get_by_id(cmd.employee_id)
        if employee is None:
            msg = f"Employee '{cmd.employee_id}' was not found."
            raise NotFoundError(msg)

        employee.update_details(
            branch_id=cmd.branch_id,
            first_name=cmd.first_name,
            last_name=cmd.last_name,
            phone_number=cmd.phone_number,
            role=cmd.role,
            email=cmd.email,
        )

        await self._employee_repo.save(employee)
        return employee
