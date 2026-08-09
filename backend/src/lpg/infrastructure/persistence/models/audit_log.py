"""SQLAlchemy ORM model for `audit.audit_log`.

Written to exclusively by `lpg.infrastructure.persistence.audit.AuditRecorder`
— nothing else constructs this model. Never exposed through the API in
Phase 2; there is no audit-read use case yet.
"""

from __future__ import annotations

# Real imports, not TYPE_CHECKING-guarded — see the identical note in
# lpg.infrastructure.persistence.models.tenant.
import uuid
from datetime import datetime  # noqa: TC003
from typing import Any

from sqlalchemy import DateTime, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lpg.infrastructure.persistence.database import Base


class AuditLogModel(Base):
    __tablename__ = "audit_log"
    __table_args__ = {"schema": "audit"}  # noqa: RUF012 - see tenant.py's identical note

    # Python-side default (not just the migration's server_default): the ORM
    # needs to know how to populate the primary key at flush time to issue a
    # correct INSERT, since AuditRecorder never sets `id` explicitly.
    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid())
    entity_name: Mapped[str] = mapped_column(String(200))
    entity_id: Mapped[str | None] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(50))
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    correlation_id: Mapped[str | None] = mapped_column(String(100))
    before_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB())
    after_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB())
    # Python attribute deliberately not named `metadata` — that name is
    # reserved by `DeclarativeBase.metadata`. `mapped_column("metadata")`
    # keeps the actual database column name correct regardless.
    audit_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB())
