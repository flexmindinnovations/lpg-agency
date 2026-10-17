"""SQLAlchemy ORM models for the `messaging` schema (ADR-054).

`uuid`/`datetime` are runtime imports for the declarative mapper, as in
`models/ai.py`.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lpg.infrastructure.persistence.database import Base


class WhatsAppMessageModel(Base):
    """Append-only message log: `SELECT, INSERT` only at the DB level."""

    __tablename__ = "whatsapp_message"
    __table_args__ = {"schema": "messaging"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE")
    )
    direction: Mapped[str] = mapped_column(String(10))
    phone_number: Mapped[str] = mapped_column(String(20))
    body: Mapped[str] = mapped_column(Text())
    wa_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class WhatsAppConversationModel(Base):
    __tablename__ = "whatsapp_conversation"
    __table_args__ = {"schema": "messaging"}  # noqa: RUF012

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE"), primary_key=True
    )
    phone_number: Mapped[str] = mapped_column(String(20), primary_key=True)
    pending_quote: Mapped[dict[str, Any] | None] = mapped_column(JSONB(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
