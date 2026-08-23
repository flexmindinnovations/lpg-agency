"""SQLAlchemy implementations of the order bounded context's repository
ports (`lpg.application.order.ports`).

All queries are automatically tenant-scoped via Row-Level Security (RLS).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from lpg.application.common.errors import NotFoundError
from lpg.application.order.ports import (
    CancellationRecordEntry,
    OrderStatusHistoryEntry,
    ProofOfDeliveryEntry,
)
from lpg.domain.order.order import DeliveryAddress, Order, OrderLine
from lpg.infrastructure.persistence.models.delivery import RouteModel, RouteStopModel
from lpg.infrastructure.persistence.models.order import (
    CancellationRecordModel,
    FailedDeliveryRecordModel,
    OrderLineModel,
    OrderModel,
    OrderStatusHistoryModel,
    ProofOfDeliveryModel,
)

if TYPE_CHECKING:
    from sqlalchemy.sql.elements import ColumnElement

    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


def _to_decimal(value: float | None) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


class SqlAlchemyOrderRepository:
    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def get_by_id(self, order_id: uuid.UUID) -> Order | None:
        stmt = (
            select(OrderModel)
            .options(selectinload(OrderModel.lines))
            .where(OrderModel.id == order_id, OrderModel.is_deleted.is_(False))
        )
        row = (await self._uow.session.execute(stmt)).scalars().first()
        return self._to_domain(row) if row is not None else None

    async def list_orders(
        self,
        skip: int = 0,
        limit: int = 50,
        status: str | None = None,
        branch_id: uuid.UUID | None = None,
        customer_id: uuid.UUID | None = None,
        driver_id: uuid.UUID | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[Order]:
        stmt = (
            select(OrderModel)
            .options(selectinload(OrderModel.lines))
            .where(*self._filters(status, branch_id, customer_id, from_date, to_date))
        )
        stmt = self._apply_driver_filter(stmt, driver_id)
        stmt = stmt.order_by(OrderModel.requested_date.desc(), OrderModel.id.desc())
        stmt = stmt.offset(skip).limit(limit)
        rows = (await self._uow.session.execute(stmt)).scalars().all()
        return [self._to_domain(row) for row in rows]

    async def count_orders(
        self,
        status: str | None = None,
        branch_id: uuid.UUID | None = None,
        customer_id: uuid.UUID | None = None,
        driver_id: uuid.UUID | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> int:
        stmt = select(func.count(OrderModel.id)).where(
            *self._filters(status, branch_id, customer_id, from_date, to_date)
        )
        stmt = self._apply_driver_filter(stmt, driver_id)
        return int((await self._uow.session.execute(stmt)).scalar_one())

    @staticmethod
    def _apply_driver_filter(stmt: Any, driver_id: uuid.UUID | None) -> Any:
        """`Order` has no `driver_id` column (Phase 12 — see `route_stop_id`);
        "this driver's orders" is reached by joining through
        `delivery.route_stop` -> `delivery.route`.
        """
        if driver_id is None:
            return stmt
        return (
            stmt.join(RouteStopModel, RouteStopModel.id == OrderModel.route_stop_id)
            .join(RouteModel, RouteModel.id == RouteStopModel.route_id)
            .where(RouteModel.driver_id == driver_id)
        )

    async def list_status_history(self, order_id: uuid.UUID) -> list[OrderStatusHistoryEntry]:
        stmt = (
            select(OrderStatusHistoryModel)
            .where(OrderStatusHistoryModel.order_id == order_id)
            .order_by(OrderStatusHistoryModel.changed_at.asc())
        )
        rows = (await self._uow.session.execute(stmt)).scalars().all()
        return [
            OrderStatusHistoryEntry(
                id=row.id,
                order_id=row.order_id,
                from_status=row.from_status,
                to_status=row.to_status,
                changed_by=row.changed_by,
                changed_at=row.changed_at,
                reason=row.reason,
            )
            for row in rows
        ]

    @staticmethod
    def _filters(
        status: str | None,
        branch_id: uuid.UUID | None,
        customer_id: uuid.UUID | None,
        from_date: datetime | None,
        to_date: datetime | None,
    ) -> list[ColumnElement[bool]]:
        clauses: list[ColumnElement[bool]] = [OrderModel.is_deleted.is_(False)]
        if status is not None:
            clauses.append(OrderModel.status == status)
        if branch_id is not None:
            clauses.append(OrderModel.branch_id == branch_id)
        if customer_id is not None:
            clauses.append(OrderModel.customer_id == customer_id)
        if from_date is not None:
            clauses.append(OrderModel.requested_date >= from_date)
        if to_date is not None:
            clauses.append(OrderModel.requested_date <= to_date)
        return clauses

    def _to_domain(self, row: OrderModel) -> Order:
        delivery_address = DeliveryAddress(
            address_line=row.delivery_address_line,
            latitude=float(row.delivery_latitude) if row.delivery_latitude is not None else None,
            longitude=float(row.delivery_longitude) if row.delivery_longitude is not None else None,
        )
        lines = [
            OrderLine(
                line_id=line.id,
                cylinder_type_id=line.cylinder_type_id,
                quantity_ordered=line.quantity_ordered,
                unit_price=line.unit_price,
                quantity_delivered=line.quantity_delivered,
                quantity_pending=line.quantity_pending,
                quantity_collected_empty=line.quantity_collected_empty,
                is_backordered=line.is_backordered,
            )
            for line in row.lines
        ]
        order = Order(
            order_id=row.id,
            tenant_id=row.tenant_id,
            order_number=row.order_number,
            branch_id=row.branch_id,
            customer_id=row.customer_id,
            address_id=row.address_id,
            delivery_address=delivery_address,
            booking_source=row.booking_source,
            requested_date=row.requested_date,
            lines=lines,
            payment_method_preference=row.payment_method_preference,
            metadata=row.metadata_json,
            status=row.status,
            route_stop_id=row.route_stop_id,
            total_amount=row.total_amount,
            version=row.version,
        )
        self._uow.register_aggregate(order)
        return order

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    async def save(self, order: Order) -> None:
        stmt = select(OrderModel).where(OrderModel.id == order.id)
        row = (await self._uow.session.execute(stmt)).scalars().first()

        delivery_address = order.delivery_address
        if row is None:
            row = OrderModel(
                id=order.id,
                tenant_id=order.tenant_id,
                order_number=order.order_number,
                branch_id=order.branch_id,
                customer_id=order.customer_id,
                address_id=order.address_id,
                delivery_address_line=delivery_address.address_line,
                delivery_latitude=_to_decimal(delivery_address.latitude),
                delivery_longitude=_to_decimal(delivery_address.longitude),
                status=order.status,
                booking_source=order.booking_source,
                payment_method_preference=order.payment_method_preference,
                requested_date=order.requested_date,
                metadata_json=order.metadata,
                route_stop_id=order.route_stop_id,
                total_amount=order.total_amount,
            )
            self._uow.session.add(row)
            # Flush now so the order row is INSERTed before any line/history
            # rows that FK-reference it — same cross-table ordering
            # reasoning as `SqlAlchemyInventoryLocationRepository.save()`.
            await self._uow.session.flush()
        else:
            row.status = order.status
            row.route_stop_id = order.route_stop_id
            row.total_amount = order.total_amount
            row.metadata_json = order.metadata
            row.updated_at = datetime.now(UTC)
            row.version += 1

        # Lines are only ever added at Order construction, never removed —
        # sync is select-or-insert-then-update-in-place per line id.
        line_stmt = select(OrderLineModel).where(OrderLineModel.order_id == order.id)
        existing_lines = {
            line_row.id: line_row
            for line_row in (await self._uow.session.execute(line_stmt)).scalars()
        }
        for line in order.lines:
            line_row = existing_lines.get(line.id)
            if line_row is None:
                self._uow.session.add(
                    OrderLineModel(
                        id=line.id,
                        order_id=order.id,
                        cylinder_type_id=line.cylinder_type_id,
                        quantity_ordered=line.quantity_ordered,
                        quantity_delivered=line.quantity_delivered,
                        quantity_pending=line.quantity_pending,
                        quantity_collected_empty=line.quantity_collected_empty,
                        is_backordered=line.is_backordered,
                        unit_price=line.unit_price,
                    )
                )
            else:
                line_row.quantity_delivered = line.quantity_delivered
                line_row.quantity_pending = line.quantity_pending
                line_row.quantity_collected_empty = line.quantity_collected_empty
                line_row.is_backordered = line.is_backordered
                line_row.unit_price = line.unit_price

        for entry in order.pending_status_history:
            self._uow.session.add(
                OrderStatusHistoryModel(
                    order_id=order.id,
                    from_status=entry.from_status,
                    to_status=entry.to_status,
                    changed_by=entry.changed_by,
                    reason=entry.reason,
                )
            )
        order.clear_pending_status_history()

        for failed_entry in order.pending_failed_delivery_entries:
            self._uow.session.add(
                FailedDeliveryRecordModel(
                    order_id=order.id,
                    reason_code=failed_entry.reason_code,
                    resolution_action=failed_entry.resolution_action,
                    recorded_by=failed_entry.recorded_by,
                )
            )
        order.clear_pending_failed_delivery_entries()

        await self._uow.session.flush()


class SqlAlchemyCancellationRecordRepository:
    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    async def create(
        self,
        *,
        record_id: uuid.UUID,
        tenant_id: uuid.UUID,
        order_id: uuid.UUID,
        cancelled_by: uuid.UUID,
        reason: str,
    ) -> CancellationRecordEntry:
        row = CancellationRecordModel(
            id=record_id,
            tenant_id=tenant_id,
            order_id=order_id,
            cancelled_by=cancelled_by,
            reason=reason,
        )
        self._uow.session.add(row)
        await self._uow.session.flush()
        return self._to_entry(row)

    async def get_pending_by_order_id(self, order_id: uuid.UUID) -> CancellationRecordEntry | None:
        stmt = select(CancellationRecordModel).where(
            CancellationRecordModel.order_id == order_id,
            CancellationRecordModel.approved_by.is_(None),
            CancellationRecordModel.is_deleted.is_(False),
        )
        row = (await self._uow.session.execute(stmt)).scalars().first()
        return self._to_entry(row) if row is not None else None

    async def approve(
        self, record_id: uuid.UUID, *, approved_by: uuid.UUID, cancellation_charge: Decimal
    ) -> CancellationRecordEntry:
        stmt = select(CancellationRecordModel).where(
            CancellationRecordModel.id == record_id,
            CancellationRecordModel.is_deleted.is_(False),
        )
        row = (await self._uow.session.execute(stmt)).scalars().first()
        if row is None:
            msg = f"Cancellation record {record_id} not found."
            raise NotFoundError(msg)

        row.approved_by = approved_by
        row.cancellation_charge = cancellation_charge
        row.approved_at = datetime.now(UTC)
        row.updated_at = datetime.now(UTC)
        row.version += 1
        await self._uow.session.flush()
        return self._to_entry(row)

    @staticmethod
    def _to_entry(row: CancellationRecordModel) -> CancellationRecordEntry:
        return CancellationRecordEntry(
            id=row.id,
            tenant_id=row.tenant_id,
            order_id=row.order_id,
            cancelled_by=row.cancelled_by,
            approved_by=row.approved_by,
            cancellation_charge=row.cancellation_charge,
            reason=row.reason,
            requested_at=row.requested_at,
            approved_at=row.approved_at,
        )


class SqlAlchemyProofOfDeliveryRepository:
    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    async def create(
        self,
        *,
        pod_id: uuid.UUID,
        tenant_id: uuid.UUID,
        order_id: uuid.UUID,
        otp_verified_at: datetime,
        signature_blob_ref: str,
        photo_blob_ref: str,
        gps_lat: Decimal,
        gps_lng: Decimal,
        payment_method: str,
        amount_collected: Decimal,
        recorded_by: uuid.UUID,
    ) -> ProofOfDeliveryEntry:
        row = ProofOfDeliveryModel(
            id=pod_id,
            tenant_id=tenant_id,
            order_id=order_id,
            otp_verified_at=otp_verified_at,
            signature_blob_ref=signature_blob_ref,
            photo_blob_ref=photo_blob_ref,
            gps_lat=gps_lat,
            gps_lng=gps_lng,
            payment_method=payment_method,
            amount_collected=amount_collected,
            recorded_by=recorded_by,
        )
        self._uow.session.add(row)
        await self._uow.session.flush()
        return ProofOfDeliveryEntry(
            id=row.id,
            tenant_id=row.tenant_id,
            order_id=row.order_id,
            otp_verified_at=row.otp_verified_at,
            signature_blob_ref=row.signature_blob_ref,
            photo_blob_ref=row.photo_blob_ref,
            gps_lat=row.gps_lat,
            gps_lng=row.gps_lng,
            payment_method=row.payment_method,
            amount_collected=row.amount_collected,
            recorded_by=row.recorded_by,
            recorded_at=row.recorded_at,
        )
