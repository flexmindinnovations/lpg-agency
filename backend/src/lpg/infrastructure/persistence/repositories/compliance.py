"""SQLAlchemy implementation of `ScaleRepository`.

All queries are tenant-scoped via Row-Level Security on `compliance.scale`.
Implements `lpg.application.compliance.ports.ScaleRepository`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import Select, func, select

from lpg.domain.compliance.scale import Scale
from lpg.infrastructure.persistence.models.compliance import ScaleModel

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
