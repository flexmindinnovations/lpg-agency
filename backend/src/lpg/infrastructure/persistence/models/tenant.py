"""SQLAlchemy ORM models for the `tenant` schema — `tenant.tenant`,
`tenant.branch`, `tenant.warehouse`, `tenant.cylinder_type`.

Deliberately distinct from the domain aggregates (`lpg.domain.tenant.*`) —
these are the persistence shape; the repository is what translates between
the two (`03-backend-architecture.md` §4).

**`created_at`/`updated_at`/`is_deleted`/`version` all declare a matching
`server_default` here, not only in the migration's DDL.** Every prior
tenant-scoped row creation in this codebase went through either a
`SECURITY DEFINER` SQL function (Identity module, Phase 6) or a raw
admin-role `INSERT` (test seeding) — Branch/Warehouse (Phase 7) are the
first plain `session.add(SomeModel(...))` ORM inserts anywhere in this
codebase. Without `server_default` mirrored here, SQLAlchemy includes every
mapped column in the `INSERT` with an explicit `NULL` for anything the
caller didn't set, instead of omitting the column and letting the
database's own default apply — found the hard way, via a real
`NotNullViolationError` on `created_at`, not a hypothetical.
"""

from __future__ import annotations

# Real imports, not TYPE_CHECKING-guarded: SQLAlchemy's declarative mapper
# resolves `Mapped[...]` annotations via `typing.get_type_hints()` at
# mapper-configuration time, which needs `uuid`/`datetime` present in this
# module's runtime namespace — unlike a plain dataclass, hiding them behind
# `if TYPE_CHECKING:` breaks the mapping.
import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003
from decimal import Decimal  # noqa: TC003
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lpg.infrastructure.persistence.database import Base


class TenantModel(Base):
    """Maps every column the migration created, not only the ones this
    phase's repository happens to touch — an ORM model with gaps against its
    own table is exactly what makes a later `alembic revision --autogenerate`
    propose dropping columns nobody meant to remove."""

    __tablename__ = "tenant"
    # SQLAlchemy's own declarative base already types __table_args__ as an
    # instance attribute; annotating it ClassVar here to satisfy ruff's
    # RUF012 (mutable class default) conflicts with that under
    # mypy --strict. SQLAlchemy only ever reads this once, at
    # mapper-configuration time — it is not a mutable-default footgun in
    # practice, so the rule is suppressed rather than fought.
    __table_args__ = {"schema": "tenant"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20))
    subscription_plan: Mapped[str] = mapped_column(String(50))
    primary_contact_email: Mapped[str] = mapped_column(String(320))
    country: Mapped[str] = mapped_column(String(2))
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


class BranchModel(Base):
    """Maps `tenant.branch` (migration `c3e8f1a5b6d7`)."""

    __tablename__ = "branch"
    __table_args__ = {"schema": "tenant"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid())
    name: Mapped[str] = mapped_column(String(200))
    region: Mapped[str | None] = mapped_column(String(200))
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


class WarehouseModel(Base):
    """Maps `tenant.warehouse` (migration `c3e8f1a5b6d7`)."""

    __tablename__ = "warehouse"
    __table_args__ = {"schema": "tenant"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid())
    branch_id: Mapped[uuid.UUID] = mapped_column(Uuid())
    name: Mapped[str] = mapped_column(String(200))
    address_line: Mapped[str] = mapped_column(String(500))
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


class CylinderTypeModel(Base):
    """Maps `tenant.cylinder_type` (migration `d4f9a2b8e1c6`)."""

    __tablename__ = "cylinder_type"
    __table_args__ = {"schema": "tenant"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid())
    name: Mapped[str] = mapped_column(String(200))
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(precision=6, scale=2))
    is_active: Mapped[bool] = mapped_column(Boolean(), server_default=text("true"))
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


class TenantConfigurationModel(Base):
    """Maps `tenant.tenant_configuration` (migration `e5a1c7d3f9b2`).

    Append-only — no `updated_at`/`updated_by`/`is_deleted`/`deleted_at`/
    `deleted_by`/`version`, matching the table's own SELECT/INSERT-only
    grant (a row is never updated or deleted, only superseded by a later
    `effective_from` row).
    """

    __tablename__ = "tenant_configuration"
    __table_args__ = {"schema": "tenant"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid())
    config_key: Mapped[str] = mapped_column(String(100))
    config_value: Mapped[Any] = mapped_column(JSONB())
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid())


class PriceListModel(Base):
    """Maps `tenant.price_list` (migration `f6b2d8e4a0c7`). Append-only —
    same shape as `TenantConfigurationModel`.
    """

    __tablename__ = "price_list"
    __table_args__ = {"schema": "tenant"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid())
    cylinder_type_id: Mapped[uuid.UUID] = mapped_column(Uuid())
    customer_type: Mapped[str] = mapped_column(String(20))
    branch_id: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    price: Mapped[Decimal] = mapped_column(Numeric(precision=10, scale=2))
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid())


class FeatureFlagOverrideModel(Base):
    """Maps `tenant.feature_flag_override` (migration `a7c3e9f5b1d8`).

    Lives in this module, not `models/platform.py`, because it is mapped to
    a `tenant`-schema table — the persistence-schema boundary decides file
    placement here, not the `platform` bounded context it belongs to
    conceptually (see `lpg.domain.platform.feature_flag`'s module docstring).
    """

    __tablename__ = "feature_flag_override"
    __table_args__ = {"schema": "tenant"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid())
    flag_key: Mapped[str] = mapped_column(String(100))
    is_enabled: Mapped[bool] = mapped_column(Boolean())
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
