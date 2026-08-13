"""SQLAlchemy implementation of VehicleRepository.

All queries are automatically tenant-scoped via Row-Level Security (RLS).
Implements `lpg.application.delivery.ports.VehicleRepository`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, or_, select

from lpg.domain.delivery.vehicle import Vehicle
from lpg.infrastructure.persistence.models.delivery import VehicleModel

if TYPE_CHECKING:
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyVehicleRepository:
    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    # ------------------------------------------------------------------
    # Mapping helpers
    # ------------------------------------------------------------------

    def _to_domain(self, row: VehicleModel) -> Vehicle:
        vehicle = Vehicle(
            vehicle_id=row.id,
            tenant_id=row.tenant_id,
            branch_id=row.branch_id,
            registration_number=row.registration_number,
            make=row.make,
            model=row.model,
            ownership_type=row.ownership_type,
            capacity_units=row.capacity_units,
            status=row.status,
            version=row.version,
        )
        vehicle.clear_events()
        self._uow.register_aggregate(vehicle)
        return vehicle

    def _sync_row(self, row: VehicleModel, vehicle: Vehicle) -> None:
        """Apply domain state to an existing ORM row (update path)."""
        row.registration_number = vehicle.registration_number
        row.make = vehicle.make
        row.model = vehicle.model
        row.ownership_type = vehicle.ownership_type
        row.capacity_units = vehicle.capacity_units
        row.status = vehicle.status
        row.updated_at = datetime.now(UTC)
        row.version = vehicle.version

    # ------------------------------------------------------------------
    # Repository methods
    # ------------------------------------------------------------------

    async def get_by_id(self, vehicle_id: uuid.UUID) -> Vehicle | None:
        stmt = select(VehicleModel).where(
            VehicleModel.id == vehicle_id,
            VehicleModel.is_deleted.is_(False),
        )
        result = await self._uow.session.execute(stmt)
        row = result.scalars().first()
        return self._to_domain(row) if row is not None else None

    async def get_by_registration_number(self, registration_number: str) -> Vehicle | None:
        stmt = select(VehicleModel).where(
            VehicleModel.registration_number == registration_number,
            VehicleModel.is_deleted.is_(False),
        )
        result = await self._uow.session.execute(stmt)
        row = result.scalars().first()
        return self._to_domain(row) if row is not None else None

    async def save(self, vehicle: Vehicle) -> None:
        stmt = select(VehicleModel).where(VehicleModel.id == vehicle.id)
        row = (await self._uow.session.execute(stmt)).scalars().first()

        if row is None:
            row = VehicleModel(
                id=vehicle.id,
                tenant_id=vehicle.tenant_id,
                branch_id=vehicle.branch_id,
                registration_number=vehicle.registration_number,
                make=vehicle.make,
                model=vehicle.model,
                ownership_type=vehicle.ownership_type,
                capacity_units=vehicle.capacity_units,
                status=vehicle.status,
            )
            self._uow.session.add(row)
        else:
            self._sync_row(row, vehicle)

    async def list_vehicles(
        self,
        skip: int = 0,
        limit: int = 50,
        search: str | None = None,
        status: str | None = None,
        branch_id: uuid.UUID | None = None,
    ) -> list[Vehicle]:
        stmt = select(VehicleModel).where(VehicleModel.is_deleted.is_(False))

        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    VehicleModel.registration_number.ilike(pattern),
                    VehicleModel.make.ilike(pattern),
                    VehicleModel.model.ilike(pattern),
                )
            )
        if status:
            stmt = stmt.where(VehicleModel.status == status)
        if branch_id:
            stmt = stmt.where(VehicleModel.branch_id == branch_id)

        stmt = stmt.order_by(VehicleModel.registration_number).offset(skip).limit(limit)
        result = await self._uow.session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def count_vehicles(
        self,
        search: str | None = None,
        status: str | None = None,
        branch_id: uuid.UUID | None = None,
    ) -> int:
        stmt = (
            select(func.count()).select_from(VehicleModel).where(VehicleModel.is_deleted.is_(False))
        )
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    VehicleModel.registration_number.ilike(pattern),
                    VehicleModel.make.ilike(pattern),
                    VehicleModel.model.ilike(pattern),
                )
            )
        if status:
            stmt = stmt.where(VehicleModel.status == status)
        if branch_id:
            stmt = stmt.where(VehicleModel.branch_id == branch_id)

        result = await self._uow.session.execute(stmt)
        return result.scalar_one()

    async def count_by_status(self) -> dict[str, int]:
        stmt = (
            select(VehicleModel.status, func.count())
            .where(VehicleModel.is_deleted.is_(False))
            .group_by(VehicleModel.status)
        )
        result = await self._uow.session.execute(stmt)
        return {status: int(count) for status, count in result.all()}
