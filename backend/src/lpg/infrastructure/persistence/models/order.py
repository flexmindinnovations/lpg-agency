"""SQLAlchemy ORM models for the orders schema.

Maps the 6 `orders.*` tables to Python objects.

IMPORTANT — runtime type imports:
SQLAlchemy's declarative mapper resolves `Mapped[...]` annotations via
`typing.get_type_hints()` at mapper-configuration time, which needs `uuid`
and `datetime` to be present in this module's runtime namespace. Hiding them
behind `if TYPE_CHECKING:` breaks the mapping (see `models/inventory.py`'s
identical note — this exact mistake has recurred twice in this codebase).
"""

from __future__ import annotations

import uuid
from datetime import datetime  # noqa: TC003
from decimal import Decimal  # noqa: TC003
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lpg.infrastructure.persistence.database import Base


class OrderModel(Base):
    __tablename__ = "order"
    __table_args__ = {"schema": "orders"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE")
    )
    order_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.branch.id", ondelete="CASCADE")
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid(), ForeignKey("customer.customer.id"))
    address_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("customer.customer_address.id")
    )
    delivery_address_line: Mapped[str] = mapped_column(Text())
    delivery_latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    delivery_longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    status: Mapped[str] = mapped_column(String(30), server_default="draft")
    booking_source: Mapped[str] = mapped_column(String(20))
    payment_method_preference: Mapped[str | None] = mapped_column(String(20), nullable=True)
    requested_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # `key=` must match the Python attribute name explicitly: `mapper.columns`
    # (used by `AuditRecorder._capture_state`'s `getattr(obj, column.key)`)
    # exposes the raw `Column.key`, which defaults to the DB column name
    # ("metadata") rather than this attribute's name — and `Base.metadata`
    # already exists as a class attribute (SQLAlchemy's own MetaData
    # registry), so an unqualified `getattr(obj, "metadata")` silently
    # resolves to that instead of raising, corrupting the audit-log write.
    metadata_json: Mapped[Any] = mapped_column(
        "metadata", JSONB(), server_default=text("'{}'::jsonb"), key="metadata_json"
    )
    # Replaces the Phase 11 interim `driver_id`/`vehicle_id` columns —
    # Phase 12 made `delivery.route`/`route_stop` real; the assigned
    # driver/vehicle are now reached transitively via this FK.
    route_stop_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("delivery.route_stop.id"), nullable=True
    )
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    # Audit columns
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean(), server_default=text("false"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    version: Mapped[int] = mapped_column(Integer(), server_default=text("1"))

    lines: Mapped[list[OrderLineModel]] = relationship(
        "OrderLineModel", back_populates="order", cascade="all, delete-orphan", passive_deletes=True
    )


class OrderLineModel(Base):
    __tablename__ = "order_line"
    __table_args__ = {"schema": "orders"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("orders.order.id", ondelete="CASCADE")
    )
    cylinder_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.cylinder_type.id")
    )
    quantity_ordered: Mapped[int] = mapped_column(Integer())
    quantity_delivered: Mapped[int] = mapped_column(Integer(), server_default=text("0"))
    quantity_pending: Mapped[int] = mapped_column(Integer(), server_default=text("0"))
    quantity_collected_empty: Mapped[int] = mapped_column(Integer(), server_default=text("0"))
    is_backordered: Mapped[bool] = mapped_column(Boolean(), server_default=text("false"))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    order: Mapped[OrderModel] = relationship("OrderModel", back_populates="lines")


class OrderStatusHistoryModel(Base):
    """Append-only — no standard audit columns, matching `audit.audit_log`
    and `inventory.inventory_transaction`'s precedent. UPDATE/DELETE are
    revoked from the app role at the database level.
    """

    __tablename__ = "order_status_history"
    __table_args__ = {"schema": "orders"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("orders.order.id", ondelete="CASCADE")
    )
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str] = mapped_column(String(30))
    changed_by: Mapped[uuid.UUID] = mapped_column(Uuid())
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    reason: Mapped[str | None] = mapped_column(Text(), nullable=True)


class FailedDeliveryRecordModel(Base):
    """Append-only — see `OrderStatusHistoryModel`'s identical note."""

    __tablename__ = "failed_delivery_record"
    __table_args__ = {"schema": "orders"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("orders.order.id", ondelete="CASCADE")
    )
    reason_code: Mapped[str] = mapped_column(String(30))
    resolution_action: Mapped[str | None] = mapped_column(String(20), nullable=True)
    recorded_by: Mapped[uuid.UUID] = mapped_column(Uuid())
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class CancellationRecordModel(Base):
    """Mutated exactly once (`approve()` fills `approved_by`/
    `cancellation_charge`/`approved_at`) — unlike the other order entities,
    this one keeps normal audit columns and normal grants.
    """

    __tablename__ = "cancellation_record"
    __table_args__ = {"schema": "orders"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE")
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("orders.order.id", ondelete="CASCADE")
    )
    cancelled_by: Mapped[uuid.UUID] = mapped_column(Uuid())
    approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    cancellation_charge: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    reason: Mapped[str] = mapped_column(Text())
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Audit columns
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean(), server_default=text("false"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    version: Mapped[int] = mapped_column(Integer(), server_default=text("1"))


class ProofOfDeliveryModel(Base):
    """Append-only, exactly one row per order — see
    `OrderStatusHistoryModel`'s identical note.
    """

    __tablename__ = "proof_of_delivery"
    __table_args__ = {"schema": "orders"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE")
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("orders.order.id", ondelete="CASCADE")
    )
    otp_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    signature_blob_ref: Mapped[str] = mapped_column(Text())
    photo_blob_ref: Mapped[str] = mapped_column(Text())
    gps_lat: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    gps_lng: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    payment_method: Mapped[str] = mapped_column(String(20))
    amount_collected: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    recorded_by: Mapped[uuid.UUID] = mapped_column(Uuid())
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
