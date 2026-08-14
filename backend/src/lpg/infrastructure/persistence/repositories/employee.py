"""SQLAlchemy implementation of EmployeeRepository.

All queries are automatically tenant-scoped via Row-Level Security (RLS).
The RLS policy on `tenant.employee` uses `current_setting('app.current_tenant_id')`,
which is set transaction-scoped by the UnitOfWork's `__aenter__` via the
tenant middleware before any query executes.

Implements `lpg.application.tenant_admin.ports.EmployeeRepository`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, or_, select

if TYPE_CHECKING:
    from collections.abc import Sequence

from lpg.domain.tenant_admin.employee import Employee
from lpg.infrastructure.persistence.models.tenant import EmployeeModel

if TYPE_CHECKING:
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyEmployeeRepository:
    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    async def next_employee_code(self) -> str:
        stmt = select(func.nextval("tenant.employee_code_seq"))
        result = await self._uow.session.execute(stmt)
        seq_val = result.scalar_one()
        return f"EMP{seq_val:04d}"

    # ------------------------------------------------------------------
    # Mapping helpers
    # ------------------------------------------------------------------

    def _to_domain(self, row: EmployeeModel) -> Employee:
        employee = Employee(
            employee_id=row.id,
            tenant_id=row.tenant_id,
            branch_id=row.branch_id,
            employee_code=row.employee_code,
            first_name=row.first_name,
            last_name=row.last_name,
            phone_number=row.phone_number,
            email=row.email,
            role=row.role,
            status=row.status,
            version=row.version,
        )
        employee.clear_events()
        self._uow.register_aggregate(employee)
        return employee

    def _sync_row(self, row: EmployeeModel, employee: Employee) -> None:
        """Apply domain state to an existing ORM row (update path)."""
        row.branch_id = employee.branch_id
        row.first_name = employee.first_name
        row.last_name = employee.last_name
        row.phone_number = employee.phone_number
        row.email = employee.email
        row.role = employee.role
        row.status = employee.status
        row.updated_at = datetime.now(UTC)
        row.version = employee.version

    # ------------------------------------------------------------------
    # Repository methods
    # ------------------------------------------------------------------

    async def get_by_id(self, employee_id: uuid.UUID) -> Employee | None:
        stmt = select(EmployeeModel).where(
            EmployeeModel.id == employee_id,
            EmployeeModel.is_deleted.is_(False),
        )
        result = await self._uow.session.execute(stmt)
        row = result.scalars().first()
        return self._to_domain(row) if row is not None else None

    async def get_by_employee_code(self, employee_code: str) -> Employee | None:
        stmt = select(EmployeeModel).where(
            EmployeeModel.employee_code == employee_code,
            EmployeeModel.is_deleted.is_(False),
        )
        result = await self._uow.session.execute(stmt)
        row = result.scalars().first()
        return self._to_domain(row) if row is not None else None

    async def save(self, employee: Employee) -> None:
        stmt = select(EmployeeModel).where(EmployeeModel.id == employee.id)
        row = (await self._uow.session.execute(stmt)).scalars().first()

        if row is None:
            row = EmployeeModel(
                id=employee.id,
                tenant_id=employee.tenant_id,
                branch_id=employee.branch_id,
                employee_code=employee.employee_code,
                first_name=employee.first_name,
                last_name=employee.last_name,
                phone_number=employee.phone_number,
                email=employee.email,
                role=employee.role,
                status=employee.status,
            )
            self._uow.session.add(row)
        else:
            self._sync_row(row, employee)

    async def list_employees(
        self,
        skip: int = 0,
        limit: int = 50,
        search: str | None = None,
        role: str | None = None,
        branch_id: uuid.UUID | None = None,
    ) -> Sequence[Employee]:
        stmt = select(EmployeeModel).where(EmployeeModel.is_deleted.is_(False))

        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    EmployeeModel.employee_code.ilike(pattern),
                    EmployeeModel.first_name.ilike(pattern),
                    EmployeeModel.last_name.ilike(pattern),
                    EmployeeModel.phone_number.ilike(pattern),
                    EmployeeModel.email.ilike(pattern),
                )
            )
        if role:
            stmt = stmt.where(EmployeeModel.role == role)
        if branch_id:
            stmt = stmt.where(EmployeeModel.branch_id == branch_id)

        stmt = stmt.order_by(EmployeeModel.created_at.desc()).offset(skip).limit(limit)
        result = await self._uow.session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def count_employees(
        self,
        search: str | None = None,
        role: str | None = None,
        branch_id: uuid.UUID | None = None,
    ) -> int:
        stmt = (
            select(func.count()).select_from(EmployeeModel).where(EmployeeModel.is_deleted.is_(False))
        )
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    EmployeeModel.employee_code.ilike(pattern),
                    EmployeeModel.first_name.ilike(pattern),
                    EmployeeModel.last_name.ilike(pattern),
                    EmployeeModel.phone_number.ilike(pattern),
                    EmployeeModel.email.ilike(pattern),
                )
            )
        if role:
            stmt = stmt.where(EmployeeModel.role == role)
        if branch_id:
            stmt = stmt.where(EmployeeModel.branch_id == branch_id)

        result = await self._uow.session.execute(stmt)
        return result.scalar_one()
