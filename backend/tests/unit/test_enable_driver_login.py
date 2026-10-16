"""Unit tests for `EnableDriverLoginUseCase`.

The use case only decides *whether* an employee may get a driver login (right
tenant, exists, is a driver, is active) and then delegates to the
`DriverLoginProvisioner` port; creating the login and linking the driver
profile is covered against a real database in
`tests/integration/test_enable_driver_login.py`.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from lpg.application.common.errors import (
    ApplicationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from lpg.application.common.tenant import RequestTenantContext
from lpg.application.tenant_admin.ports import DriverLoginResult
from lpg.application.tenant_admin.use_cases.enable_driver_login import (
    EnableDriverLoginCommand,
    EnableDriverLoginUseCase,
)
from lpg.domain.tenant_admin.employee import Employee

if TYPE_CHECKING:
    from collections.abc import Sequence


TENANT_ID = uuid.uuid4()


def _employee(**kwargs: object) -> Employee:
    defaults: dict[str, object] = {
        "employee_id": uuid.uuid4(),
        "tenant_id": TENANT_ID,
        "branch_id": uuid.uuid4(),
        "employee_code": "EMP-1005",
        "first_name": "Vijay",
        "last_name": "Naidu",
        "phone_number": "+919848011005",
        "role": "driver",
    }
    defaults.update(kwargs)
    return Employee(**defaults)  # type: ignore[arg-type]


class _FakeEmployeeRepository:
    def __init__(self, employees: Sequence[Employee]) -> None:
        self._by_id = {e.id: e for e in employees}

    def next_id(self) -> uuid.UUID:
        raise NotImplementedError

    async def next_employee_code(self, tenant_id: uuid.UUID) -> str:
        raise NotImplementedError

    async def get_by_id(self, employee_id: uuid.UUID) -> Employee | None:
        return self._by_id.get(employee_id)

    async def get_by_employee_code(self, employee_code: str) -> Employee | None:
        raise NotImplementedError

    async def save(self, employee: Employee) -> None:
        raise NotImplementedError

    async def list_employees(
        self,
        skip: int = 0,
        limit: int = 50,
        search: str | None = None,
        status: str | None = None,
        role: str | None = None,
        branch_id: uuid.UUID | None = None,
    ) -> Sequence[Employee]:
        raise NotImplementedError

    async def count_employees(
        self,
        search: str | None = None,
        status: str | None = None,
        role: str | None = None,
        branch_id: uuid.UUID | None = None,
    ) -> int:
        raise NotImplementedError


class _FakeProvisioner:
    def __init__(self) -> None:
        self.calls: list[tuple[uuid.UUID, Employee]] = []
        self.result = DriverLoginResult(
            user_id=uuid.uuid4(),
            driver_id=uuid.uuid4(),
            login_created=True,
            driver_created=False,
        )

    async def enable(self, tenant_id: uuid.UUID, employee: Employee) -> DriverLoginResult:
        self.calls.append((tenant_id, employee))
        return self.result


def _use_case(
    employees: Sequence[Employee], provisioner: _FakeProvisioner
) -> EnableDriverLoginUseCase:
    return EnableDriverLoginUseCase(
        RequestTenantContext(tenant_id=TENANT_ID), _FakeEmployeeRepository(employees), provisioner
    )


class TestEnableDriverLogin:
    async def test_delegates_to_the_provisioner_for_an_active_driver(self) -> None:
        employee = _employee()
        provisioner = _FakeProvisioner()

        result = await _use_case([employee], provisioner).execute(
            EnableDriverLoginCommand(tenant_id=TENANT_ID, employee_id=employee.id)
        )

        assert result is provisioner.result
        assert provisioner.calls == [(TENANT_ID, employee)]

    async def test_unknown_employee_is_not_found(self) -> None:
        provisioner = _FakeProvisioner()

        with pytest.raises(NotFoundError):
            await _use_case([], provisioner).execute(
                EnableDriverLoginCommand(tenant_id=TENANT_ID, employee_id=uuid.uuid4())
            )

        assert provisioner.calls == []

    @pytest.mark.parametrize("role", ["manager", "dispatcher", "accountant", "warehouse_staff"])
    async def test_staff_roles_are_rejected_because_they_sign_in_to_the_dashboard(
        self, role: str
    ) -> None:
        employee = _employee(role=role)
        provisioner = _FakeProvisioner()

        with pytest.raises(ValidationError, match="Users & Roles"):
            await _use_case([employee], provisioner).execute(
                EnableDriverLoginCommand(tenant_id=TENANT_ID, employee_id=employee.id)
            )

        assert provisioner.calls == []

    @pytest.mark.parametrize("status", ["on_leave", "inactive"])
    async def test_inactive_employees_are_rejected(self, status: str) -> None:
        employee = _employee(status=status)
        provisioner = _FakeProvisioner()

        with pytest.raises(ConflictError, match="active employee"):
            await _use_case([employee], provisioner).execute(
                EnableDriverLoginCommand(tenant_id=TENANT_ID, employee_id=employee.id)
            )

        assert provisioner.calls == []

    async def test_a_command_for_another_tenant_is_forbidden(self) -> None:
        employee = _employee()
        provisioner = _FakeProvisioner()

        with pytest.raises(ApplicationError, match="Cross-tenant"):
            await _use_case([employee], provisioner).execute(
                EnableDriverLoginCommand(tenant_id=uuid.uuid4(), employee_id=employee.id)
            )

        assert provisioner.calls == []
