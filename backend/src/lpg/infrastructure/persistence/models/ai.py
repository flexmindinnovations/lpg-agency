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
from decimal import Decimal  # noqa: TC003
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, Text, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
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


class PredictionModel(Base):
    """Append-only — one row every time a heuristic (Horizon 1) or a trained
    model (Horizon 2) produces a number shown to a user. Same "never edited
    after creation" shape as `AssistantRunModel` / `WeighmentRecordModel`:
    a corrected prediction is a new row with a new `model_version`, not an
    update. `SELECT, INSERT` only at the DB level (the creating migration).

    This is the traceability spine of AI Operational Intelligence — every
    displayed prediction is attributable to the exact model that produced
    it, and a heuristic → model swap is observable in the history.
    """

    __tablename__ = "prediction"
    __table_args__ = {"schema": "ai"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("tenant.tenant.id", ondelete="CASCADE")
    )
    prediction_type: Mapped[str] = mapped_column(String(50))
    subject_type: Mapped[str] = mapped_column(String(50))
    subject_id: Mapped[uuid.UUID] = mapped_column(Uuid())
    model_version: Mapped[str] = mapped_column(String(100))
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB())
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
