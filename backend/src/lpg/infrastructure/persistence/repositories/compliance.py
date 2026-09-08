"""SQLAlchemy implementation of `ScaleRepository`.

All queries are tenant-scoped via Row-Level Security on `compliance.scale`.
Implements `lpg.application.compliance.ports.ScaleRepository`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import Select, case, desc, func, select

from lpg.application.compliance.ports import OrderFulfillmentRecord
from lpg.domain.compliance.cylinder_unit import CylinderUnit
from lpg.domain.compliance.scale import Scale
from lpg.domain.compliance.weighment_record import WeighmentRecord
from lpg.infrastructure.persistence.models.compliance import (
    CylinderUnitModel,
    ScaleModel,
    WeighmentRecordModel,
)
from lpg.infrastructure.persistence.models.order import OrderModel, OrderStatusHistoryModel

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


class SqlAlchemyCylinderUnitRepository:
    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------

    def _to_domain(self, row: CylinderUnitModel) -> CylinderUnit:
        unit = CylinderUnit(
            cylinder_unit_id=row.id,
            tenant_id=row.tenant_id,
            cylinder_type_id=row.cylinder_type_id,
            serial_number=row.serial_number,
            condition_status=row.condition_status,
            custody_type=row.custody_type,
            custody_ref_id=row.custody_ref_id,
            manufacture_date=row.manufacture_date,
            owner_omc=row.owner_omc,
            last_tested_at=row.last_tested_at,
            test_due_date=row.test_due_date,
            is_retired=row.is_retired,
            version=row.version,
        )
        unit.clear_events()
        self._uow.register_aggregate(unit)
        return unit

    def _sync_row(self, row: CylinderUnitModel, unit: CylinderUnit) -> None:
        row.cylinder_type_id = unit.cylinder_type_id
        row.serial_number = unit.serial_number
        row.manufacture_date = unit.manufacture_date
        row.owner_omc = unit.owner_omc
        row.condition_status = unit.condition_status
        row.custody_type = unit.custody_type
        row.custody_ref_id = unit.custody_ref_id
        row.last_tested_at = unit.last_tested_at
        row.test_due_date = unit.test_due_date
        row.is_retired = unit.is_retired
        row.updated_at = datetime.now(UTC)
        row.version = unit.version

    # ------------------------------------------------------------------
    # Repository methods
    # ------------------------------------------------------------------

    async def save(self, unit: CylinderUnit) -> None:
        stmt = select(CylinderUnitModel).where(CylinderUnitModel.id == unit.id)
        row = (await self._uow.session.execute(stmt)).scalars().first()
        if row is None:
            self._uow.session.add(
                CylinderUnitModel(
                    id=unit.id,
                    tenant_id=unit.tenant_id,
                    cylinder_type_id=unit.cylinder_type_id,
                    serial_number=unit.serial_number,
                    manufacture_date=unit.manufacture_date,
                    owner_omc=unit.owner_omc,
                    condition_status=unit.condition_status,
                    custody_type=unit.custody_type,
                    custody_ref_id=unit.custody_ref_id,
                    last_tested_at=unit.last_tested_at,
                    test_due_date=unit.test_due_date,
                    is_retired=unit.is_retired,
                )
            )
        else:
            self._sync_row(row, unit)

    async def get_by_id(self, unit_id: uuid.UUID) -> CylinderUnit | None:
        stmt = select(CylinderUnitModel).where(
            CylinderUnitModel.id == unit_id, CylinderUnitModel.is_deleted.is_(False)
        )
        row = (await self._uow.session.execute(stmt)).scalars().first()
        return self._to_domain(row) if row is not None else None

    async def get_by_serial(self, serial_number: str) -> CylinderUnit | None:
        stmt = select(CylinderUnitModel).where(
            CylinderUnitModel.serial_number == serial_number,
            CylinderUnitModel.is_deleted.is_(False),
        )
        row = (await self._uow.session.execute(stmt)).scalars().first()
        return self._to_domain(row) if row is not None else None

    def _list_for_tenant_stmt(
        self,
        *,
        due_status: str | None,
        cylinder_type_id: uuid.UUID | None,
        custody_type: str | None,
    ) -> Select[tuple[CylinderUnitModel]]:
        stmt = select(CylinderUnitModel).where(
            CylinderUnitModel.is_deleted.is_(False), CylinderUnitModel.is_retired.is_(False)
        )
        if cylinder_type_id is not None:
            stmt = stmt.where(CylinderUnitModel.cylinder_type_id == cylinder_type_id)
        if custody_type is not None:
            stmt = stmt.where(CylinderUnitModel.custody_type == custody_type)

        today = datetime.now(UTC).date()
        if due_status == "overdue":
            stmt = stmt.where(CylinderUnitModel.test_due_date < today)
        elif due_status == "due_soon":
            stmt = stmt.where(
                CylinderUnitModel.test_due_date >= today,
                CylinderUnitModel.test_due_date <= today + timedelta(days=30),
            )
        return stmt

    async def list_for_tenant(
        self,
        *,
        due_status: str | None = None,
        cylinder_type_id: uuid.UUID | None = None,
        custody_type: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[CylinderUnit]:
        stmt = (
            self._list_for_tenant_stmt(
                due_status=due_status, cylinder_type_id=cylinder_type_id, custody_type=custody_type
            )
            .order_by(CylinderUnitModel.test_due_date.asc().nullslast())
            .offset(skip)
            .limit(limit)
        )
        rows = (await self._uow.session.execute(stmt)).scalars().all()
        return [self._to_domain(row) for row in rows]

    async def count_for_tenant(
        self,
        *,
        due_status: str | None = None,
        cylinder_type_id: uuid.UUID | None = None,
        custody_type: str | None = None,
    ) -> int:
        inner = self._list_for_tenant_stmt(
            due_status=due_status, cylinder_type_id=cylinder_type_id, custody_type=custody_type
        ).subquery()
        stmt = select(func.count()).select_from(inner)
        return (await self._uow.session.execute(stmt)).scalar_one()


class SqlAlchemyTdtRatingRepository:
    """Implements `TdtRatingRepository`. Reads `orders.order_status_history`
    joined to `orders.order` — tenant isolation comes entirely from
    Row-Level Security on the `orders.order` side of that join (see the
    port's own docstring: `order_status_history` carries no `tenant_id`
    column or RLS policy of its own)."""

    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    async def get_fulfillment_records(
        self,
        quarter_start: datetime,
        quarter_end: datetime,
        *,
        branch_id: uuid.UUID | None = None,
    ) -> list[OrderFulfillmentRecord]:
        """Two passes, not one filtered-then-grouped query: an order's
        `booked` transition can land in an earlier quarter than its
        `delivered` one (any turnaround slower than same-quarter), so
        filtering `order_status_history` rows by `changed_at` *before*
        aggregating would silently drop that `booked` row whenever it
        falls outside the window — corrupting the elapsed-days calculation
        for exactly the slow deliveries this metric exists to catch. TDT
        rates by *when the delivery happened*, not by requiring every
        event in an order's timeline to fall in the same quarter.

        Step 1 finds the order IDs with a `delivered` transition inside
        `[quarter_start, quarter_end)` — this *is* the "exclude cancelled/
        still-in-flight orders from this pass" policy (an open question,
        see the source plan): an order that was cancelled or hasn't
        reached `delivered` yet simply never appears here, full stop.
        Step 2 aggregates each of those orders' *entire* history (no
        window filter) to recover its true `booked_at`, whenever that
        actually happened.
        """
        delivered_in_window = select(OrderStatusHistoryModel.order_id).where(
            OrderStatusHistoryModel.to_status == "delivered",
            OrderStatusHistoryModel.changed_at >= quarter_start,
            OrderStatusHistoryModel.changed_at < quarter_end,
        )

        booked_at = func.max(
            case(
                (OrderStatusHistoryModel.to_status == "booked", OrderStatusHistoryModel.changed_at)
            )
        )
        delivered_at = func.max(
            case(
                (
                    OrderStatusHistoryModel.to_status == "delivered",
                    OrderStatusHistoryModel.changed_at,
                )
            )
        )
        stmt = (
            select(
                OrderModel.id,
                OrderModel.branch_id,
                booked_at.label("booked_at"),
                delivered_at.label("delivered_at"),
            )
            .select_from(OrderStatusHistoryModel)
            .join(OrderModel, OrderModel.id == OrderStatusHistoryModel.order_id)
            .where(
                OrderModel.is_deleted.is_(False),
                OrderStatusHistoryModel.order_id.in_(delivered_in_window),
            )
            .group_by(OrderModel.id, OrderModel.branch_id)
            # Defensive, not expected to ever trigger: every order's own
            # transition graph requires passing through `booked` before it
            # can ever reach `delivered` (domain.order.order's
            # _TRANSITIONS), so a delivered order missing a booked_at
            # would indicate corrupt history data, not a normal case.
            .having(booked_at.is_not(None))
        )
        if branch_id is not None:
            stmt = stmt.where(OrderModel.branch_id == branch_id)

        rows = (await self._uow.session.execute(stmt)).all()
        return [
            OrderFulfillmentRecord(
                order_id=row.id,
                branch_id=row.branch_id,
                booked_at=row.booked_at,
                delivered_at=row.delivered_at,
            )
            for row in rows
        ]
