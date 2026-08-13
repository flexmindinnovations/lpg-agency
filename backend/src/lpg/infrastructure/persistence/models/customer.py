from __future__ import annotations

# Real imports, not TYPE_CHECKING-guarded: SQLAlchemy's declarative mapper
# resolves `Mapped[...]` annotations via `typing.get_type_hints()` at
# mapper-configuration time, which needs `uuid`/`datetime`/`Decimal` present
# in this module's runtime namespace — hiding them behind `if TYPE_CHECKING:`
# breaks the mapping (see `models/tenant.py`'s identical note).
import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003
from decimal import Decimal  # noqa: TC003

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lpg.infrastructure.persistence.database import Base


class CustomerModel(Base):
    __tablename__ = "customer"
    __table_args__ = {"schema": "customer"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE")
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.branch.id", ondelete="CASCADE")
    )
    consumer_number: Mapped[str] = mapped_column(String(50))
    full_name: Mapped[str] = mapped_column(String(200))
    phone_number: Mapped[str] = mapped_column(String(20))
    customer_type: Mapped[str] = mapped_column(String(50), server_default="domestic")
    kyc_status: Mapped[str] = mapped_column(String(50), server_default="pending")
    status: Mapped[str] = mapped_column(String(50), server_default="active")
    lpg_subsidy_id: Mapped[str | None] = mapped_column(String(17))
    identity_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)

    # Audit Columns
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    is_deleted: Mapped[bool] = mapped_column(Boolean(), server_default=text("false"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    version: Mapped[int] = mapped_column(Integer(), server_default=text("1"))

    # Relationships
    addresses: Mapped[list[CustomerAddressModel]] = relationship(
        "CustomerAddressModel",
        back_populates="customer",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    kyc_documents: Mapped[list[KycDocumentModel]] = relationship(
        "KycDocumentModel",
        back_populates="customer",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class CustomerAddressModel(Base):
    __tablename__ = "customer_address"
    __table_args__ = {"schema": "customer"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE")
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("customer.customer.id", ondelete="CASCADE")
    )
    address_line: Mapped[str] = mapped_column(Text())
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(precision=9, scale=6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(precision=9, scale=6))
    is_primary: Mapped[bool] = mapped_column(Boolean(), server_default=text("false"))

    # Audit Columns
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    is_deleted: Mapped[bool] = mapped_column(Boolean(), server_default=text("false"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    version: Mapped[int] = mapped_column(Integer(), server_default=text("1"))

    # Relationships
    customer: Mapped[CustomerModel] = relationship("CustomerModel", back_populates="addresses")


class KycDocumentModel(Base):
    __tablename__ = "kyc_document"
    __table_args__ = {"schema": "customer"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE")
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("customer.customer.id", ondelete="CASCADE")
    )
    doc_type: Mapped[str] = mapped_column(String(50))
    doc_reference: Mapped[str] = mapped_column(Text())
    verification_status: Mapped[str] = mapped_column(String(50), server_default="pending")
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("identity.identity_user.id", ondelete="SET NULL")
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Audit Columns
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    is_deleted: Mapped[bool] = mapped_column(Boolean(), server_default=text("false"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    version: Mapped[int] = mapped_column(Integer(), server_default=text("1"))

    # Relationships
    customer: Mapped[CustomerModel] = relationship("CustomerModel", back_populates="kyc_documents")


class CustomerNumberSequenceModel(Base):
    """One row per tenant — the counter `SqlAlchemyConsumerNumberSequence`
    advances via `INSERT ... ON CONFLICT ... DO UPDATE ... RETURNING`.
    """

    __tablename__ = "customer_number_sequence"
    __table_args__ = {"schema": "customer"}  # noqa: RUF012

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE"), primary_key=True
    )
    next_value: Mapped[int] = mapped_column(Integer(), server_default=text("1"))
