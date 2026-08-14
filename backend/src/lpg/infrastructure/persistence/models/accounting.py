"""SQLAlchemy ORM models for the accounting schema.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lpg.infrastructure.persistence.database import Base

if TYPE_CHECKING:
    import uuid


class InvoiceModel(Base):
    __tablename__ = "invoice"
    __table_args__ = {"schema": "accounting"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE")
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid(), ForeignKey("customer.customer.id"))
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("orders.order.id"), unique=True
    )
    status: Mapped[str] = mapped_column(String(30))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer(), server_default=text("1"))

    # Relationships
    lines: Mapped[list[InvoiceLineModel]] = relationship(
        "InvoiceLineModel",
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="InvoiceLineModel.id",
    )


class InvoiceLineModel(Base):
    __tablename__ = "invoice_line"
    __table_args__ = {"schema": "accounting"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("accounting.invoice.id", ondelete="CASCADE")
    )
    cylinder_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.cylinder_type.id")
    )
    quantity: Mapped[int] = mapped_column(Integer())
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))

    invoice: Mapped[InvoiceModel] = relationship(
        "InvoiceModel", back_populates="lines"
    )
