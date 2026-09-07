"""SQLAlchemy implementation of `ScaleRepository`.

All queries are tenant-scoped via Row-Level Security on `compliance.scale`.
Implements `lpg.application.compliance.ports.ScaleRepository`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import Select, desc, func, select

from lpg.domain.compliance.scale import Scale
from lpg.domain.compliance.weighment_record import WeighmentRecord
from lpg.infrastructure.persistence.models.compliance import (
    ScaleModel,
    WeighmentRecordModel,
)

if TYPE_CHECKING:
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyScaleRepository:
    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------

    def _to_domain(self, row: ScaleModel) -> Scale:
        scale = Scale(
            scale_id=row.id,
            tenant_id=row.tenant_id,
            warehouse_id=row.warehouse_id,
            asset_tag=row.asset_tag,
            least_count_grams=row.least_count_grams,
            certificate_ref=row.certificate_ref,
            certificate_expiry_date=row.certificate_expiry_date,
            make=row.make,
            model=row.model,
            status=row.status,
            version=row.version,
        )
        scale.clear_events()
        self._uow.register_aggregate(scale)
        return scale

    def _sync_row(self, row: ScaleModel, scale: Scale) -> None:
        row.asset_tag = scale.asset_tag
        row.make = scale.make
        row.model = scale.model
        row.least_count_grams = scale.least_count_grams
        row.certificate_ref = scale.certificate_ref
        row.certificate_expiry_date = scale.certificate_expiry_date
        row.status = scale.status
        row.updated_at = datetime.now(UTC)
        row.version = scale.version

    # ------------------------------------------------------------------
    # Repository methods
    # ------------------------------------------------------------------

    async def save(self, scale: Scale) -> None:
        stmt = select(ScaleModel).where(ScaleModel.id == scale.id)
        row = (await self._uow.session.execute(stmt)).scalars().first()
        if row is None:
            self._uow.session.add(
                ScaleModel(
                    id=scale.id,
                    tenant_id=scale.tenant_id,
                    warehouse_id=scale.warehouse_id,
                    asset_tag=scale.asset_tag,
                    make=scale.make,
                    model=scale.model,
                    least_count_grams=scale.least_count_grams,
                    certificate_ref=scale.certificate_ref,
                    certificate_expiry_date=scale.certificate_expiry_date,
                    status=scale.status,
                )
            )
        else:
            self._sync_row(row, scale)

    async def get_by_id(self, scale_id: uuid.UUID) -> Scale | None:
        stmt = select(ScaleModel).where(
            ScaleModel.id == scale_id, ScaleModel.is_deleted.is_(False)
        )
        row = (await self._uow.session.execute(stmt)).scalars().first()
        return self._to_domain(row) if row is not None else None

    async def get_by_warehouse_and_asset_tag(
        self, warehouse_id: uuid.UUID, asset_tag: str
    ) -> Scale | None:
        stmt = select(ScaleModel).where(
            ScaleModel.warehouse_id == warehouse_id,
            ScaleModel.asset_tag == asset_tag,
            ScaleModel.is_deleted.is_(False),
        )
        row = (await self._uow.session.execute(stmt)).scalars().first()
        return self._to_domain(row) if row is not None else None

    async def list_for_warehouse(self, warehouse_id: uuid.UUID) -> list[Scale]:
        stmt = (
            select(ScaleModel)
            .where(ScaleModel.warehouse_id == warehouse_id, ScaleModel.is_deleted.is_(False))
            .order_by(ScaleModel.asset_tag)
        )
        rows = (await self._uow.session.execute(stmt)).scalars().all()
        return [self._to_domain(row) for row in rows]

    def _list_for_tenant_stmt(
        self, *, status: str | None, expiry: str | None
    ) -> Select[tuple[ScaleModel]]:
        stmt = select(ScaleModel).where(ScaleModel.is_deleted.is_(False))
        if status:
            stmt = stmt.where(ScaleModel.status == status)

        today = datetime.now(UTC).date()
        if expiry == "expired":
            stmt = stmt.where(ScaleModel.certificate_expiry_date < today)
        elif expiry == "expiring":
            stmt = stmt.where(
                ScaleModel.certificate_expiry_date >= today,
                ScaleModel.certificate_expiry_date <= today + timedelta(days=30),
            )
        return stmt

    async def list_for_tenant(
        self,
        *,
        status: str | None = None,
        expiry: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Scale]:
        stmt = (
            self._list_for_tenant_stmt(status=status, expiry=expiry)
            .order_by(ScaleModel.certificate_expiry_date.asc().nullslast())
            .offset(skip)
            .limit(limit)
        )
        rows = (await self._uow.session.execute(stmt)).scalars().all()
        return [self._to_domain(row) for row in rows]

    async def count_for_tenant(
        self, *, status: str | None = None, expiry: str | None = None
    ) -> int:
        inner = self._list_for_tenant_stmt(status=status, expiry=expiry).subquery()
        stmt = select(func.count()).select_from(inner)
        return (await self._uow.session.execute(stmt)).scalar_one()


class SqlAlchemyWeighmentRecordRepository:
    """Append-only — no `save`/update path, matching `WeighmentRecord`'s own
    shape. No `register_aggregate`/event-dispatch either: this is a plain
    entity, not an `AggregateRoot`."""

    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    def _to_domain(self, row: WeighmentRecordModel) -> WeighmentRecord:
        return WeighmentRecord(
            id=row.id,
            tenant_id=row.tenant_id,
            scale_id=row.scale_id,
            context=row.context,
            reference_type=row.reference_type,
            reference_id=row.reference_id,
            cylinder_type_id=row.cylinder_type_id,
            total_cylinders_in_batch=row.total_cylinders_in_batch,
            cylinders_checked=row.cylinders_checked,
            underweight_cylinder_count=row.underweight_cylinder_count,
            tolerance_grams_applied=row.tolerance_grams_applied,
            result=row.result,
            recorded_by=row.recorded_by,
            recorded_at=row.recorded_at,
        )

    async def add(self, record: WeighmentRecord) -> None:
        self._uow.session.add(
            WeighmentRecordModel(
                id=record.id,
                tenant_id=record.tenant_id,
                scale_id=record.scale_id,
                context=record.context,
                reference_type=record.reference_type,
                reference_id=record.reference_id,
                cylinder_type_id=record.cylinder_type_id,
                total_cylinders_in_batch=record.total_cylinders_in_batch,
                cylinders_checked=record.cylinders_checked,
                underweight_cylinder_count=record.underweight_cylinder_count,
                tolerance_grams_applied=record.tolerance_grams_applied,
                result=record.result,
                recorded_by=record.recorded_by,
                recorded_at=record.recorded_at,
            )
        )

    async def list_for_reference(
        self, reference_type: str, reference_id: uuid.UUID
    ) -> list[WeighmentRecord]:
        stmt = (
            select(WeighmentRecordModel)
            .where(
                WeighmentRecordModel.reference_type == reference_type,
                WeighmentRecordModel.reference_id == reference_id,
            )
            .order_by(desc(WeighmentRecordModel.recorded_at))
        )
        rows = (await self._uow.session.execute(stmt)).scalars().all()
        return [self._to_domain(row) for row in rows]

    async def get_latest_passing_for_reference(
        self, reference_type: str, reference_id: uuid.UUID, *, context: str
    ) -> WeighmentRecord | None:
        stmt = (
            select(WeighmentRecordModel)
            .where(
                WeighmentRecordModel.reference_type == reference_type,
                WeighmentRecordModel.reference_id == reference_id,
                WeighmentRecordModel.context == context,
                WeighmentRecordModel.result == "pass",
            )
            .order_by(desc(WeighmentRecordModel.recorded_at))
            .limit(1)
        )
        row = (await self._uow.session.execute(stmt)).scalars().first()
        return self._to_domain(row) if row is not None else None
