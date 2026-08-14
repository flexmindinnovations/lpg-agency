"""SQLAlchemy implementation of DriverRepository.

All queries are automatically tenant-scoped via Row-Level Security (RLS).
The RLS policy on `delivery.driver` uses `current_setting('app.current_tenant_id')`,
which is set transaction-scoped by the UnitOfWork's `__aenter__` via the
tenant middleware before any query executes.

Implements `lpg.application.delivery.ports.DriverRepository`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from lpg.domain.delivery.driver import Driver
from lpg.infrastructure.persistence.models.delivery import DriverModel

if TYPE_CHECKING:
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyDriverRepository:
    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    # ------------------------------------------------------------------
    # Mapping helpers
    # ------------------------------------------------------------------

    def _to_domain(self, row: DriverModel) -> Driver:
        driver = Driver(
            driver_id=row.id,
            tenant_id=row.tenant_id,
            branch_id=row.branch_id,
            identity_user_id=row.identity_user_id,
            employee_id=row.employee_id,
            license_number=row.license_number,
            license_expiry_date=row.license_expiry_date,
            status=row.status,
            version=row.version,
        )
        # Reconstruct clears the events recorded during __init__; we do not
        # want to re-dispatch DriverRegistered for rows loaded from the DB.
        driver.clear_events()
        self._uow.register_aggregate(driver)
        return driver

    def _sync_row(self, row: DriverModel, driver: Driver) -> None:
        """Apply domain state to an existing ORM row (update path)."""
        row.identity_user_id = driver.identity_user_id
        row.employee_id = driver.employee_id
        row.license_number = driver.license_number
        row.license_expiry_date = driver.license_expiry_date
        row.status = driver.status
        row.updated_at = datetime.now(UTC)
        row.version = driver.version

    # ------------------------------------------------------------------
    # Repository methods
    # ------------------------------------------------------------------

    async def get_by_id(self, driver_id: uuid.UUID) -> Driver | None:
        stmt = select(DriverModel).where(
            DriverModel.id == driver_id,
            DriverModel.is_deleted.is_(False),
        )
        result = await self._uow.session.execute(stmt)
        row = result.scalars().first()
        return self._to_domain(row) if row is not None else None

    async def get_by_employee_id(self, employee_id: uuid.UUID) -> Driver | None:
        stmt = select(DriverModel).where(
            DriverModel.employee_id == employee_id,
            DriverModel.is_deleted.is_(False),
        )
        result = await self._uow.session.execute(stmt)
        row = result.scalars().first()
        return self._to_domain(row) if row is not None else None

    async def get_by_identity_user_id(self, identity_user_id: uuid.UUID) -> Driver | None:
        stmt = select(DriverModel).where(
            DriverModel.identity_user_id == identity_user_id,
            DriverModel.is_deleted.is_(False),
        )
        result = await self._uow.session.execute(stmt)
        row = result.scalars().first()
        return self._to_domain(row) if row is not None else None

    async def save(self, driver: Driver) -> None:
        stmt = select(DriverModel).where(DriverModel.id == driver.id)
        row = (await self._uow.session.execute(stmt)).scalars().first()

        if row is None:
            row = DriverModel(
                id=driver.id,
                tenant_id=driver.tenant_id,
                branch_id=driver.branch_id,
                identity_user_id=driver.identity_user_id,
                employee_id=driver.employee_id,
                license_number=driver.license_number,
                license_expiry_date=driver.license_expiry_date,
                status=driver.status,
            )
            self._uow.session.add(row)
        else:
            self._sync_row(row, driver)

    async def list_drivers(
        self,
        skip: int = 0,
        limit: int = 50,
        search: str | None = None,
        status: str | None = None,
        branch_id: uuid.UUID | None = None,
    ) -> list[Driver]:
        stmt = select(DriverModel).where(DriverModel.is_deleted.is_(False))

        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(DriverModel.license_number.ilike(pattern))
        if status:
            stmt = stmt.where(DriverModel.status == status)
        if branch_id:
            stmt = stmt.where(DriverModel.branch_id == branch_id)

        stmt = stmt.order_by(DriverModel.created_at.desc()).offset(skip).limit(limit)
        result = await self._uow.session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def count_drivers(
        self,
        search: str | None = None,
        status: str | None = None,
        branch_id: uuid.UUID | None = None,
    ) -> int:
        stmt = (
            select(func.count()).select_from(DriverModel).where(DriverModel.is_deleted.is_(False))
        )
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(DriverModel.license_number.ilike(pattern))
        if status:
            stmt = stmt.where(DriverModel.status == status)
        if branch_id:
            stmt = stmt.where(DriverModel.branch_id == branch_id)

        result = await self._uow.session.execute(stmt)
        return result.scalar_one()
