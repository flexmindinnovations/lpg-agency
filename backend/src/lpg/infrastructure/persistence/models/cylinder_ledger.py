"""SQLAlchemy ORM models for the cylinder_ledger schema."""

from __future__ import annotations

import uuid
from datetime import datetime  # noqa: TC003

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from lpg.infrastructure.persistence.database import Base


class CylinderLedgerModel(Base):
    __tablename__ = "cylinder_ledger"
    __table_args__ = {"schema": "cylinder_ledger"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE")
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("customer.customer.id", ondelete="CASCADE")
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


class LedgerTransactionModel(Base):
    """Append-only transaction ledger row."""
    __tablename__ = "ledger_transaction"
    __table_args__ = {"schema": "cylinder_ledger"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE")
    )
    cylinder_ledger_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("cylinder_ledger.cylinder_ledger.id", ondelete="CASCADE")
    )
    cylinder_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.cylinder_type.id")
    )
    transaction_type: Mapped[str] = mapped_column(String(30))
    quantity: Mapped[int] = mapped_column(Integer())
    reference_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    performed_by: Mapped[uuid.UUID] = mapped_column(Uuid())
    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class CylinderBalanceModel(Base):
    """Materialized projection of a customer's balance for a specific cylinder type."""
    __tablename__ = "cylinder_balance"
    __table_args__ = {"schema": "cylinder_ledger"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE")
    )
    cylinder_ledger_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("cylinder_ledger.cylinder_ledger.id", ondelete="CASCADE")
    )
    cylinder_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.cylinder_type.id")
    )
    quantity: Mapped[int] = mapped_column(Integer(), server_default=text("0"))
    last_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("cylinder_ledger.ledger_transaction.id"), nullable=True
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
