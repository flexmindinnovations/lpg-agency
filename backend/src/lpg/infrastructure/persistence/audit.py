"""Audit-row writing via a SQLAlchemy ``before_flush`` session event
(``03-backend-architecture.md`` §3: "AuditLoggingBehavior → SQLAlchemy
session event hooks capturing before/after state; audit rows written in the
Unit of Work commit path").

Generic by construction: it inspects whatever ORM models are new, dirty, or
deleted in the session at flush time — not per-model custom code — so a
future aggregate's repository needs to do nothing extra to be audited. It
operates on the *persistence* model (SQLAlchemy classes), which is what
"before/after state" means here; the domain aggregate is a separate concern
already covered by domain events (``lpg.infrastructure.events.dispatcher``).

Registered once per ``SqlAlchemyUnitOfWork`` (one per transaction), on that
transaction's session. Fires automatically inside ``session.flush()`` — no
call site anywhere else in application or domain code needs to know this
exists, which is the entire point of a session-level hook over "remember to
call the audit function."
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import event, inspect

from lpg.config.logging import get_logger
from lpg.infrastructure.persistence.models.audit_log import AuditLogModel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import Session

    from lpg.application.common.ports import TenantContext
    from lpg.infrastructure.persistence.database import Base

_logger = get_logger(__name__)


def _jsonable(value: object) -> object:
    """Coerce a mapped-column value into something JSONB can store.

    ``Decimal`` (any ``numeric`` column — cylinder weights, prices, tax
    rates) is stringified rather than converted to ``float``: an audit trail
    exists precisely to be an exact historical record, and `float` would
    silently introduce rounding a financial/measurement value should never
    have. Found via a real `TypeError` the first time an aggregate with a
    `Decimal` field (`CylinderType.weight_kg`, Phase 7) went through this
    hook — no prior aggregate had one.
    """
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _snapshot(obj: Base) -> dict[str, Any]:
    """Current values of every mapped column, as a JSON-able dict."""
    mapper = inspect(obj).mapper
    return {column.key: _jsonable(getattr(obj, column.key)) for column in mapper.columns}


def _snapshot_before(obj: Base) -> dict[str, Any]:
    """Pre-change values of every mapped column that actually changed.

    Reads SQLAlchemy's attribute history rather than the current value —
    ``getattr`` after a mutation would just return the *new* value twice.
    Unmodified columns are omitted rather than filled from the current value,
    so ``before_state`` reflects only what genuinely changed.
    """
    state = inspect(obj)
    result: dict[str, Any] = {}
    for attr in state.mapper.column_attrs:
        history = state.attrs[attr.key].history
        if history.deleted:
            result[attr.key] = _jsonable(history.deleted[0])
    return result


def _entity_id(obj: Base) -> str | None:
    value = getattr(obj, "id", None)
    return None if value is None else str(value)


class AuditRecorder:
    """Owns the ``before_flush`` listener for one Unit of Work's session."""

    def __init__(
        self,
        session: AsyncSession,
        tenant_context: TenantContext,
        *,
        correlation_id: str | None = None,
    ) -> None:
        self._tenant_context = tenant_context
        self._correlation_id = correlation_id
        # AsyncSession wraps a sync Session, reachable via .sync_session —
        # ORM events are always registered on (and fire on) the sync side,
        # even for async usage; this is the documented SQLAlchemy 2.0 pattern.
        event.listen(session.sync_session, "before_flush", self._before_flush)

    def _before_flush(self, session: Session, _flush_context: object, _instances: object) -> None:
        for obj in list(session.new):
            if isinstance(obj, AuditLogModel):
                continue
            self._record(session, obj, action="create", before=None, after=_snapshot(obj))

        for obj in list(session.dirty):
            if isinstance(obj, AuditLogModel):
                continue
            if not session.is_modified(obj, include_collections=False):
                continue
            before = _snapshot_before(obj)
            if not before:
                continue
            self._record(session, obj, action="update", before=before, after=_snapshot(obj))

        for obj in list(session.deleted):
            if isinstance(obj, AuditLogModel):
                continue
            self._record(session, obj, action="delete", before=_snapshot(obj), after=None)

    def _record(
        self,
        session: Session,
        obj: Base,
        *,
        action: str,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
    ) -> None:
        entity_display_name = None
        if hasattr(obj, "name"):
            entity_display_name = obj.name
        elif hasattr(obj, "full_name"):
            entity_display_name = obj.full_name
        elif hasattr(obj, "consumer_number"):
            entity_display_name = obj.consumer_number

        row = AuditLogModel(
            tenant_id=self._tenant_context.tenant_id,
            actor_id=self._tenant_context.user_id,
            actor_display_name=getattr(self._tenant_context, "user_display_name", None),
            entity_name=type(obj).__tablename__,
            entity_id=_entity_id(obj),
            entity_display_name=str(entity_display_name) if entity_display_name else None,
            action=action,
            performed_at=datetime.now(UTC),
            correlation_id=self._correlation_id,
            before_state=before,
            after_state=after,
        )
        session.add(row)
        _logger.debug(
            "audit_row_queued",
            entity_name=row.entity_name,
            entity_id=row.entity_id,
            action=action,
        )
