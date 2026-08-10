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

from sqlalchemy import Boolean, DateTime, Integer, String, Uuid, text
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
