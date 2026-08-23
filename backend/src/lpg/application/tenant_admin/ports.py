"""Tenant Admin repository ports."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from lpg.domain.tenant_admin.employee import Employee


@runtime_checkable
class EmployeeRepository(Protocol):
    def next_id(self) -> uuid.UUID: ...

    async def next_employee_code(self, tenant_id: uuid.UUID) -> str: ...

    async def get_by_id(self, employee_id: uuid.UUID) -> Employee | None: ...

    async def get_by_employee_code(self, employee_code: str) -> Employee | None: ...

    async def save(self, employee: Employee) -> None: ...

    async def list_employees(
        self,
        skip: int = 0,
        limit: int = 50,
        search: str | None = None,
        status: str | None = None,
        role: str | None = None,
        branch_id: uuid.UUID | None = None,
    ) -> Sequence[Employee]: ...

    async def count_employees(
        self,
        search: str | None = None,
        status: str | None = None,
        role: str | None = None,
        branch_id: uuid.UUID | None = None,
    ) -> int: ...
