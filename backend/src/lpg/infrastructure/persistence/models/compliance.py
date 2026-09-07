"""SQLAlchemy ORM models for the `compliance` schema (Weighment Part 1).

IMPORTANT — runtime type imports:
SQLAlchemy's declarative mapper resolves `Mapped[...]` annotations via
`typing.get_type_hints()` at mapper-configuration time, which needs `uuid`,
`datetime`, `date` to be present in this module's runtime namespace. Hiding
them behind `if TYPE_CHECKING:` breaks the mapping (see `models/delivery.py`'s
identical note).
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


class ScaleModel(Base):
    """A registered weighing scale at a warehouse. `warehouse_id` is a real FK
    to `tenant.warehouse` — a scale only ever lives at a warehouse, never a
    vehicle, so there's no polymorphism to model (unlike
    `inventory.inventory_location.location_ref_id`)."""

    __tablename__ = "scale"
    __table_args__ = {"schema": "compliance"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE")
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(Uuid(), ForeignKey("tenant.warehouse.id"))
    asset_tag: Mapped[str] = mapped_column(String(100))
    make: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    least_count_grams: Mapped[int] = mapped_column(Integer())
    certificate_ref: Mapped[str] = mapped_column(String())
    certificate_expiry_date: Mapped[date] = mapped_column(Date())
    status: Mapped[str] = mapped_column(String(20), server_default=text("'active'"))

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
