"""SQLAlchemy ORM models for the inventory schema.

Maps the 5 `inventory.*` tables to Python objects.

IMPORTANT — runtime type imports:
SQLAlchemy's declarative mapper resolves `Mapped[...]` annotations via
`typing.get_type_hints()` at mapper-configuration time, which needs `uuid`
and `datetime` to be present in this module's runtime namespace. Hiding them
behind `if TYPE_CHECKING:` breaks the mapping (see `models/delivery.py`'s
identical note — this exact mistake has recurred twice in this codebase).
"""

from __future__ import annotations

import uuid
from datetime import datetime  # noqa: TC003

from sqlalchemy import Boolean, Computed, DateTime, ForeignKey, Integer, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from lpg.infrastructure.persistence.database import Base
from lpg.infrastructure.persistence.models.tenant import (  # noqa: F401
    CylinderTypeModel,
    TenantModel,
    WarehouseModel,
)


class InventoryLocationModel(Base):
    __tablename__ = "inventory_location"
    __table_args__ = {"schema": "inventory"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE")
    )
    location_type: Mapped[str] = mapped_column(String(20))
    location_ref_id: Mapped[uuid.UUID] = mapped_column(Uuid())

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


class InventoryTransactionModel(Base):
    """Append-only ledger — no standard audit columns, matching `audit.audit_log`.

    UPDATE/DELETE are revoked from the app role at the database level; never
    call `.update()`/`.delete()` against this table from repository code.
    """

    __tablename__ = "inventory_transaction"
    __table_args__ = {"schema": "inventory"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE")
    )
    inventory_location_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("inventory.inventory_location.id")
    )
    cylinder_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.cylinder_type.id")
    )
    transaction_type: Mapped[str] = mapped_column(String(20))
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[int] = mapped_column(Integer())
    reference_order_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    performed_by: Mapped[uuid.UUID] = mapped_column(Uuid())
    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class InventoryBalanceModel(Base):
    """Materialized `(location, cylinder_type, status) -> quantity` projection.

    Written only in the same flush as the `InventoryTransactionModel` row
    that justifies the change — see
    `SqlAlchemyInventoryLocationRepository.save()`.
    """

    __tablename__ = "inventory_balance"
    __table_args__ = {"schema": "inventory"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE")
    )
    inventory_location_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("inventory.inventory_location.id")
    )
    cylinder_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.cylinder_type.id")
    )
    status: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[int] = mapped_column(Integer(), server_default=text("0"))
    last_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("inventory.inventory_transaction.id"), nullable=True
    )

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


class GoodsReceiptNoteModel(Base):
    __tablename__ = "goods_receipt_note"
    __table_args__ = {"schema": "inventory"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE")
    )
    grn_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(Uuid(), ForeignKey("tenant.warehouse.id"))
    cylinder_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.cylinder_type.id")
    )
    quantity_received: Mapped[int] = mapped_column(Integer())
    source_omc: Mapped[str | None] = mapped_column(String(20), nullable=True)
    received_by: Mapped[uuid.UUID] = mapped_column(Uuid())
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

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


class ReconciliationRecordModel(Base):
    __tablename__ = "reconciliation_record"
    __table_args__ = {"schema": "inventory"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE")
    )
    inventory_location_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("inventory.inventory_location.id")
    )
    cylinder_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.cylinder_type.id")
    )
    status: Mapped[str] = mapped_column(String(20))
    expected_quantity: Mapped[int] = mapped_column(Integer())
    actual_quantity: Mapped[int] = mapped_column(Integer())
    # DB-generated (`GENERATED ALWAYS AS ... STORED`) — Computed() tells
    # SQLAlchemy to exclude it from INSERT/UPDATE, matching the migration.
    variance: Mapped[int] = mapped_column(
        Integer(), Computed("actual_quantity - expected_quantity")
    )
    recorded_by: Mapped[uuid.UUID] = mapped_column(Uuid())
    approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
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
