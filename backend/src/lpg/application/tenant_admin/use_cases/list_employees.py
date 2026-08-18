import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from lpg.application.tenant_admin.ports import EmployeeRepository
    from lpg.domain.tenant_admin.employee import Employee


@dataclass
class ListEmployeesQuery:
    skip: int = 0
    limit: int = 50
    search: str | None = None
    role: str | None = None
    branch_id: uuid.UUID | None = None


class ListEmployeesUseCase:
    def __init__(self, repository: "EmployeeRepository") -> None:
        self._repository = repository

    async def execute(
        self, query: ListEmployeesQuery
    ) -> tuple["Sequence[Employee]", int]:
        try:
            employees = await self._repository.list_employees(
                skip=query.skip,
                limit=query.limit,
                search=query.search,
                role=query.role,
                branch_id=query.branch_id,
            )
            total = await self._repository.count_employees(
                search=query.search,
                role=query.role,
                branch_id=query.branch_id,
            )
            return employees, total
        except Exception as e:
            print(f"Error: {e}")
            raise e
