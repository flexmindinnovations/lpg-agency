"""SQLAlchemy ORM model for the `ai` schema (ADR-045).

IMPORTANT — runtime type imports: SQLAlchemy's declarative mapper resolves
`Mapped[...]` annotations via `typing.get_type_hints()` at mapper-
configuration time, which needs `uuid`/`datetime` present in this module's
runtime namespace — hiding them behind `if TYPE_CHECKING:` breaks the
mapping (see `models/compliance.py`'s identical note).
"""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from lpg.infrastructure.persistence.database import Base


class AssistantRunModel(Base):
    """Append-only — no standard audit columns, matching `WeighmentRecordModel`'s
    precedent (`compliance.weighment_record`) for a row that never changes
    after creation. `SELECT, INSERT` only granted at the DB level (the
    creating migration), no `UPDATE`/`DELETE`."""

    __tablename__ = "assistant_run"
    __table_args__ = {"schema": "ai"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(), nullable=True)
    role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    question: Mapped[str] = mapped_column(Text())
    tools_used: Mapped[list[str]] = mapped_column(JSON(), server_default=text("'[]'::json"))
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))
    prompt_tokens: Mapped[int] = mapped_column(Integer(), server_default=text("0"))
    completion_tokens: Mapped[int] = mapped_column(Integer(), server_default=text("0"))
    tool_turns: Mapped[int] = mapped_column(Integer(), server_default=text("0"))
    latency_ms: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    status: Mapped[str] = mapped_column(String(30))
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
