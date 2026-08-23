"""SQLAlchemy ORM models for the accounting schema."""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003
from decimal import Decimal  # noqa: TC003

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lpg.infrastructure.persistence.database import Base


class InvoiceModel(Base):
    __tablename__ = "invoice"
    __table_args__ = {"schema": "accounting"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE")
    )
    invoice_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid(), ForeignKey("customer.customer.id"))
    customer_consumer_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    order_id: Mapped[uuid.UUID] = mapped_column(Uuid(), ForeignKey("orders.order.id"), unique=True)
    order_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
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
    payments: Mapped[list[PaymentModel]] = relationship(
        "PaymentModel",
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="PaymentModel.collected_at",
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

    invoice: Mapped[InvoiceModel] = relationship("InvoiceModel", back_populates="lines")


class PaymentModel(Base):
    """Append-only — see `11ddf55a78ed`'s migration docstring."""

    __tablename__ = "payment"
    __table_args__ = {"schema": "accounting"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE")
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("accounting.invoice.id", ondelete="CASCADE")
    )
    method: Mapped[str] = mapped_column(String(20))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    collected_by: Mapped[uuid.UUID] = mapped_column(Uuid())
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    invoice: Mapped[InvoiceModel] = relationship("InvoiceModel", back_populates="payments")


class CashHandoverModel(Base):
    """Append-only — see `c039189dfbdc`'s migration docstring."""

    __tablename__ = "cash_handover"
    __table_args__ = {"schema": "accounting"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE")
    )
    handover_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    driver_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("delivery.driver.id", ondelete="CASCADE")
    )
    route_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("delivery.route.id", ondelete="CASCADE")
    )
    expected_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    actual_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    declared_by: Mapped[uuid.UUID] = mapped_column(Uuid())
    declared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class CreditNoteModel(Base):
    """Mutated exactly once, by approval — see `bdd1f778c21a`'s migration
    docstring.
    """

    __tablename__ = "credit_note"
    __table_args__ = {"schema": "accounting"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE")
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("accounting.invoice.id", ondelete="CASCADE")
    )
    credit_note_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    reason: Mapped[str] = mapped_column(Text())
    requested_by: Mapped[uuid.UUID] = mapped_column(Uuid())
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
