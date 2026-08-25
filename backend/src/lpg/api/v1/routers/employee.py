"""Employee endpoints (Phase 13).

Mounted under `/employee`.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from lpg.api.v1.dependencies.admin import get_employee_repository
from lpg.api.v1.dependencies.identity import require_permission
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.api.v1.schemas.employee import (
    ChangeEmployeeStatusRequest,
    EmployeePageResponse,
    EmployeeResponse,
    RegisterEmployeeRequest,
    UpdateEmployeeRequest,
)
from lpg.application.common.errors import NotFoundError
from lpg.application.common.ports import UnitOfWork
from lpg.application.identity.ports import AuthenticatedPrincipal
from lpg.application.tenant_admin.ports import EmployeeRepository
from lpg.application.tenant_admin.use_cases.change_employee_status import (
    ChangeEmployeeStatusCommand,
    ChangeEmployeeStatusUseCase,
)
from lpg.application.tenant_admin.use_cases.register_employee import (
    RegisterEmployeeCommand,
    RegisterEmployeeUseCase,
)
from lpg.application.tenant_admin.use_cases.update_employee import (
    UpdateEmployeeCommand,
    UpdateEmployeeUseCase,
)
from lpg.domain.common.base import DomainError
from lpg.domain.tenant_admin.employee import Employee

router = APIRouter(prefix="/employees", tags=["Employees"])


def _to_response(employee: Employee) -> EmployeeResponse:
    return EmployeeResponse(
        id=str(employee.id),
        tenant_id=str(employee.tenant_id),
        branch_id=str(employee.branch_id),
        employee_code=employee.employee_code,
        first_name=employee.first_name,
        last_name=employee.last_name,
        phone_number=employee.phone_number,
        role=employee.role,
        status=employee.status,
        email=employee.email,
    )


@router.post("", response_model=EmployeeResponse, status_code=201, summary="Register an employee")
async def register_employee(
    body: RegisterEmployeeRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("users:manage"))],
    repository: Annotated[EmployeeRepository, Depends(get_employee_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> EmployeeResponse:
    use_case = RegisterEmployeeUseCase(principal, unit_of_work, repository)
    employee_id = await use_case.execute(
        RegisterEmployeeCommand(
            tenant_id=principal.tenant_id,
            branch_id=uuid.UUID(body.branch_id),
            first_name=body.first_name,
            last_name=body.last_name,
            phone_number=body.phone_number,
            role=body.role,
            email=body.email,
        )
    )

    # Reload from repository to return full view
    employee = await repository.get_by_id(employee_id)
    assert employee is not None

    return EmployeeResponse(
        id=str(employee.id),
        tenant_id=str(employee.tenant_id),
        branch_id=str(employee.branch_id),
        employee_code=employee.employee_code,
        first_name=employee.first_name,
        last_name=employee.last_name,
        phone_number=employee.phone_number,
        role=employee.role,
        status=employee.status,
        email=employee.email,
    )


@router.get(
    "",
    response_model=EmployeePageResponse,
    dependencies=[Depends(require_permission("users:read"))],
)
async def list_employees(
    repository: Annotated[EmployeeRepository, Depends(get_employee_repository)],
    skip: int = 0,
    limit: int = 50,
    search: str | None = None,
    status: str | None = None,
    role: str | None = None,
    branch_id: uuid.UUID | None = None,
) -> EmployeePageResponse:
    from lpg.application.tenant_admin.use_cases.list_employees import (
        ListEmployeesQuery,
        ListEmployeesUseCase,
    )

    use_case = ListEmployeesUseCase(repository)
    employees, total = await use_case.execute(
        ListEmployeesQuery(
            skip=skip,
            limit=limit,
            search=search,
            status=status,
            role=role,
            branch_id=branch_id,
        )
    )
    page = (skip // limit) + 1 if limit else 1
    return EmployeePageResponse(
        items=[
            EmployeeResponse(
                id=str(e.id),
                tenant_id=str(e.tenant_id),
                branch_id=str(e.branch_id),
                employee_code=e.employee_code,
                first_name=e.first_name,
                last_name=e.last_name,
                phone_number=e.phone_number,
                role=e.role,
                status=e.status,
                email=e.email,
            )
            for e in employees
        ],
        total=total,
        page=page,
        page_size=limit,
    )


@router.get(
    "/{employee_id}",
    response_model=EmployeeResponse,
    dependencies=[Depends(require_permission("users:read"))],
)
async def get_employee(
    employee_id: uuid.UUID,
    repository: Annotated[EmployeeRepository, Depends(get_employee_repository)],
) -> EmployeeResponse:
    employee = await repository.get_by_id(employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail=f"Employee '{employee_id}' was not found.")
    return _to_response(employee)


@router.patch(
    "/{employee_id}",
    response_model=EmployeeResponse,
    dependencies=[Depends(require_permission("users:manage"))],
)
async def update_employee(
    employee_id: uuid.UUID,
    body: UpdateEmployeeRequest,
    repository: Annotated[EmployeeRepository, Depends(get_employee_repository)],
) -> EmployeeResponse:
    use_case = UpdateEmployeeUseCase(repository)
    try:
        employee = await use_case.execute(
            UpdateEmployeeCommand(
                employee_id=employee_id,
                branch_id=uuid.UUID(body.branch_id),
                first_name=body.first_name,
                last_name=body.last_name,
                phone_number=body.phone_number,
                role=body.role,
                email=body.email,
            )
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return _to_response(employee)


@router.patch(
    "/{employee_id}/status",
    response_model=EmployeeResponse,
    dependencies=[Depends(require_permission("users:manage"))],
)
async def change_employee_status(
    employee_id: uuid.UUID,
    body: ChangeEmployeeStatusRequest,
    repository: Annotated[EmployeeRepository, Depends(get_employee_repository)],
) -> EmployeeResponse:
    use_case = ChangeEmployeeStatusUseCase(repository)
    try:
        employee = await use_case.execute(
            ChangeEmployeeStatusCommand(employee_id=employee_id, new_status=body.status)
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return _to_response(employee)
