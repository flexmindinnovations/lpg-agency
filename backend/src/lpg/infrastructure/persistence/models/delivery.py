"""SQLAlchemy ORM models for the delivery schema.

Maps delivery.driver and delivery.vehicle PostgreSQL tables to Python objects.

IMPORTANT — runtime type imports:
SQLAlchemy's declarative mapper resolves `Mapped[...]` annotations via
`typing.get_type_hints()` at mapper-configuration time, which needs `uuid`,
`datetime`, `date` to be present in this module's runtime namespace.
Hiding them behind `if TYPE_CHECKING:` breaks the mapping (see
`models/customer.py`'s identical note).
"""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import (
    date,  # noqa: TC003
    datetime,  # noqa: TC003
)

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from lpg.infrastructure.persistence.database import Base
from lpg.infrastructure.persistence.models.tenant import BranchModel, TenantModel  # noqa: F401


class DriverModel(Base):
    __tablename__ = "driver"
    __table_args__ = {"schema": "delivery"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE")
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.branch.id", ondelete="CASCADE")
    )
    identity_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.employee.id", ondelete="CASCADE")
    )
    license_number: Mapped[str] = mapped_column(String())
    license_expiry_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    status: Mapped[str] = mapped_column(String(20), server_default="active")

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


class VehicleModel(Base):
    __tablename__ = "vehicle"
    __table_args__ = {"schema": "delivery"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE")
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.branch.id", ondelete="CASCADE")
    )
    registration_number: Mapped[str] = mapped_column(String())
    make: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(100))
    ownership_type: Mapped[str] = mapped_column(String(30), server_default="owned")
    capacity_units: Mapped[int] = mapped_column(Integer())
    status: Mapped[str] = mapped_column(String(20), server_default="active")

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


class RouteModel(Base):
    __tablename__ = "route"
    __table_args__ = {"schema": "delivery"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE")
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.branch.id", ondelete="CASCADE")
    )
    driver_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("delivery.driver.id", ondelete="CASCADE")
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("delivery.vehicle.id", ondelete="CASCADE")
    )
    route_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), server_default="planned")

    # Audit columns
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    version: Mapped[int] = mapped_column(Integer(), server_default=text("1"))


class RouteStopModel(Base):
    __tablename__ = "route_stop"
    __table_args__ = {"schema": "delivery"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    route_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("delivery.route.id", ondelete="CASCADE")
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("orders.order.id", ondelete="CASCADE")
    )
    sequence_number: Mapped[int] = mapped_column(Integer())
    status: Mapped[str] = mapped_column(String(30), server_default="pending")

    # Proof of Delivery fields
    otp_verified: Mapped[bool] = mapped_column(Boolean(), server_default=text("false"))
    signature_url: Mapped[str | None] = mapped_column(String(), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(), nullable=True)
    gps_lat: Mapped[float | None] = mapped_column(nullable=True)
    gps_lon: Mapped[float | None] = mapped_column(nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(), nullable=True)

    # Audit columns
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
