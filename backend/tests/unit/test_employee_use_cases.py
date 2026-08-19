"""Unit tests for Employee (tenant_admin) use cases.

Uses mocked repositories/UoW/tenant-context — no database required.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from lpg.application.common.errors import ApplicationError
from lpg.application.tenant_admin.use_cases.list_employees import (
    ListEmployeesQuery,
    ListEmployeesUseCase,
)
from lpg.application.tenant_admin.use_cases.register_employee import (
    RegisterEmployeeCommand,
    RegisterEmployeeUseCase,
)
from lpg.domain.tenant_admin.employee import Employee

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_employee_repo() -> MagicMock:
    repo = MagicMock()
    repo.next_id = MagicMock(return_value=uuid.uuid4())
    repo.next_employee_code = AsyncMock(return_value="EMP0001")
    repo.save = AsyncMock()
    repo.list_employees = AsyncMock(return_value=[])
    repo.count_employees = AsyncMock(return_value=0)
    return repo


@pytest.fixture
def mock_uow() -> MagicMock:
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)
    return uow


def _make_tenant_context(*, tenant_id: uuid.UUID | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.tenant_id = tenant_id or uuid.uuid4()
    return ctx


# ---------------------------------------------------------------------------
# RegisterEmployeeUseCase
# ---------------------------------------------------------------------------


class TestRegisterEmployeeUseCase:
    async def test_registers_employee_and_saves(
        self, mock_uow: MagicMock, mock_employee_repo: MagicMock
    ) -> None:
        tenant_id = uuid.uuid4()
        tenant_context = _make_tenant_context(tenant_id=tenant_id)
        command = RegisterEmployeeCommand(
            tenant_id=tenant_id,
            branch_id=uuid.uuid4(),
            first_name="Asha",
            last_name="Verma",
            phone_number="+919876543210",
            role="driver",
        )

        use_case = RegisterEmployeeUseCase(tenant_context, mock_uow, mock_employee_repo)
        employee_id = await use_case.execute(command)

        mock_employee_repo.save.assert_called_once()
        saved: Employee = mock_employee_repo.save.call_args[0][0]
        assert saved.id == employee_id
        assert saved.employee_code == "EMP0001"
        assert saved.first_name == "Asha"
        assert saved.role == "driver"

    async def test_rejects_cross_tenant_registration(
        self, mock_uow: MagicMock, mock_employee_repo: MagicMock
    ) -> None:
        tenant_context = _make_tenant_context(tenant_id=uuid.uuid4())
        command = RegisterEmployeeCommand(
            tenant_id=uuid.uuid4(),  # different from the context's tenant
            branch_id=uuid.uuid4(),
            first_name="Asha",
            last_name="Verma",
            phone_number="+919876543210",
            role="driver",
        )

        use_case = RegisterEmployeeUseCase(tenant_context, mock_uow, mock_employee_repo)

        with pytest.raises(ApplicationError, match="Cross-tenant"):
            await use_case.execute(command)

        mock_employee_repo.save.assert_not_called()

    async def test_uses_generated_id_and_code_from_repository(
        self, mock_uow: MagicMock, mock_employee_repo: MagicMock
    ) -> None:
        fixed_id = uuid.uuid4()
        mock_employee_repo.next_id = MagicMock(return_value=fixed_id)
        mock_employee_repo.next_employee_code = AsyncMock(return_value="EMP0042")

        tenant_id = uuid.uuid4()
        tenant_context = _make_tenant_context(tenant_id=tenant_id)
        command = RegisterEmployeeCommand(
            tenant_id=tenant_id,
            branch_id=uuid.uuid4(),
            first_name="Ravi",
            last_name="Kumar",
            phone_number="+919000000000",
            role="dispatcher",
            email="ravi@example.com",
        )

        use_case = RegisterEmployeeUseCase(tenant_context, mock_uow, mock_employee_repo)
        employee_id = await use_case.execute(command)

        assert employee_id == fixed_id
        saved: Employee = mock_employee_repo.save.call_args[0][0]
        assert saved.employee_code == "EMP0042"
        assert saved.email == "ravi@example.com"


# ---------------------------------------------------------------------------
# ListEmployeesUseCase
# ---------------------------------------------------------------------------


class TestListEmployeesUseCase:
    async def test_returns_employees_with_total(self, mock_employee_repo: MagicMock) -> None:
        employees = [MagicMock(spec=Employee), MagicMock(spec=Employee)]
        mock_employee_repo.list_employees = AsyncMock(return_value=employees)
        mock_employee_repo.count_employees = AsyncMock(return_value=2)

        use_case = ListEmployeesUseCase(mock_employee_repo)
        result, total = await use_case.execute(ListEmployeesQuery(skip=0, limit=50))

        assert result == employees
        assert total == 2

    async def test_passes_filters_to_repository(self, mock_employee_repo: MagicMock) -> None:
        branch_id = uuid.uuid4()
        query = ListEmployeesQuery(
            skip=10, limit=25, search="Asha", status="active", role="driver", branch_id=branch_id
        )

        use_case = ListEmployeesUseCase(mock_employee_repo)
        await use_case.execute(query)

        mock_employee_repo.list_employees.assert_called_once_with(
            skip=10, limit=25, search="Asha", status="active", role="driver", branch_id=branch_id
        )
        mock_employee_repo.count_employees.assert_called_once_with(
            search="Asha", status="active", role="driver", branch_id=branch_id
        )
