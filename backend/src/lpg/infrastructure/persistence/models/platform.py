"""SQLAlchemy ORM model for `platform.feature_flag`.

`tenant.feature_flag_override` is mapped in
`infrastructure/persistence/models/tenant.py` instead, alongside the other
`tenant`-schema tables — the persistence-schema boundary, not the
bounded-context boundary, is what determines which module a model lives in
(see `lpg.domain.platform.feature_flag`'s module docstring for why the
bounded context groups both together anyway).
"""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lpg.infrastructure.persistence.database import Base


class FeatureFlagModel(Base):
    """Maps `platform.feature_flag` (migration `a7c3e9f5b1d8`). No
    `tenant_id` — this table is deliberately not RLS-scoped.
    """

    __tablename__ = "feature_flag"
    __table_args__ = {"schema": "platform"}  # noqa: RUF012

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    description: Mapped[str] = mapped_column(String(500))
    is_enabled_by_default: Mapped[bool] = mapped_column(Boolean(), server_default=text("false"))
    rollout_percentage: Mapped[int | None] = mapped_column(Integer())
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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


class ReferenceNumberSequenceModel(Base):
    """Maps `platform.reference_number_sequence` (migration TBD) — a single
    shared, tenant-scoped counter table backing every module's
    human-readable reference number (`INV000001`, `ORD000001`, `EMP0001`,
    ...), keyed on `(tenant_id, entity_type)`. One shared table instead of
    a dedicated one per module, unlike `customer.customer_number_sequence`
    (the original, module-specific precedent this generalizes) — see
    `SqlAlchemyReferenceNumberSequence` for the upsert mechanic.
    """

    __tablename__ = "reference_number_sequence"
    __table_args__ = {"schema": "platform"}  # noqa: RUF012

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE"), primary_key=True
    )
    entity_type: Mapped[str] = mapped_column(String(30), primary_key=True)
    next_value: Mapped[int] = mapped_column(Integer(), server_default=text("1"))


class LicenseModel(Base):
    """Maps `platform.license` (migration `92e48f9bf322`) — a normal
    RLS-scoped tenant table despite its `platform`-schema location (see that
    migration's module docstring). `LoginUseCase`/`RefreshTokenUseCase` read
    this pre-auth via a `SECURITY DEFINER` SQL function instead of this ORM
    mapping, since no RLS session variable exists that early.

    `validity_period_seconds` stores the domain's `timedelta` as plain
    seconds — simplest mapping, no Postgres `INTERVAL` round-trip to reason
    about. `device_caps` is a `{app_type: max_devices | null}` JSON object;
    a missing key or `null` value both mean "unlimited"
    (`License.is_within_device_limit`).
    """

    __tablename__ = "license"
    __table_args__ = {"schema": "platform"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE"), unique=True
    )
    key_hash: Mapped[str] = mapped_column(String(128), unique=True)
    key_prefix: Mapped[str] = mapped_column(String(20))
    plan_tier: Mapped[str] = mapped_column(String(30))
    validity_period_seconds: Mapped[int] = mapped_column(Integer())
    device_caps: Mapped[Any] = mapped_column(JSONB(), server_default=text("'{}'::jsonb"))
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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


class LicenseFeatureOverrideModel(Base):
    """Maps `platform.license_feature_override` (migration `92e48f9bf322`).
    No `tenant_id` column (scoped via `license_id` instead) — genuinely
    outside RLS's scope, the same shape `identity.role_permission` has. One
    row per `(license_id, feature_key)` — enforced by a DB unique
    constraint, not mirrored here (this codebase's own convention, matching
    `FeatureFlagOverrideModel`'s equivalent uniqueness not being declared in
    the ORM model either)."""

    __tablename__ = "license_feature_override"
    __table_args__ = {"schema": "platform"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    license_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("platform.license.id", ondelete="CASCADE")
    )
    feature_key: Mapped[str] = mapped_column(String(100))
    granted: Mapped[bool] = mapped_column(Boolean())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    version: Mapped[int] = mapped_column(Integer(), server_default=text("1"))


class LinkedDeviceModel(Base):
    """Maps `platform.linked_device` (migration `92e48f9bf322`) — a normal
    RLS-scoped tenant table, one row per registered app instance
    (Customer/Driver/Warehouse app; Dashboard is never a valid `app_type`,
    see `lpg.domain.license.linked_device`)."""

    __tablename__ = "linked_device"
    __table_args__ = {"schema": "platform"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE")
    )
    license_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("platform.license.id", ondelete="CASCADE")
    )
    app_type: Mapped[str] = mapped_column(String(30))
    device_identifier: Mapped[str] = mapped_column(String(200))
    display_name: Mapped[str] = mapped_column(String(200))
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    version: Mapped[int] = mapped_column(Integer(), server_default=text("1"))
