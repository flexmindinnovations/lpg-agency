"""`SqlAlchemyAuditLogRepository` — implements `AuditLogRepository`
(`lpg.application.audit.ports`).

Read-only against `audit.audit_log` (SELECT already granted, Phase 2 — see
that migration's grants). Uses `Database.session()`, not `SqlAlchemyUnitOfWork`
— there is nothing to commit, matching every other pure-query repository's
shape (`common/cqrs.py`: "Queries bypass repositories entirely and read
through optimized paths").
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import literal, select, tuple_

from lpg.application.audit.ports import AuditLogEntry, AuditLogPage
from lpg.infrastructure.persistence.models.audit_log import AuditLogModel

if TYPE_CHECKING:
    from lpg.infrastructure.persistence.database import Database

_CURSOR_SEPARATOR = "|"


def _encode_cursor(performed_at: datetime, entry_id: uuid.UUID) -> str:
    return f"{performed_at.isoformat()}{_CURSOR_SEPARATOR}{entry_id}"


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    performed_at_iso, entry_id = cursor.rsplit(_CURSOR_SEPARATOR, 1)
    return datetime.fromisoformat(performed_at_iso), uuid.UUID(entry_id)


class SqlAlchemyAuditLogRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def get_page(
        self,
        tenant_id: uuid.UUID,
        *,
        entity_name: str | None = None,
        actor_id: uuid.UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> AuditLogPage:
        stmt = (
            select(AuditLogModel)
            .where(AuditLogModel.tenant_id == tenant_id)
            .order_by(AuditLogModel.performed_at.desc(), AuditLogModel.id.desc())
            # Fetch one extra row to know whether a next page exists,
            # without a separate COUNT(*) query.
            .limit(limit + 1)
        )
        if entity_name is not None:
            stmt = stmt.where(AuditLogModel.entity_name == entity_name)
        if actor_id is not None:
            stmt = stmt.where(AuditLogModel.actor_id == actor_id)
        if date_from is not None:
            stmt = stmt.where(AuditLogModel.performed_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(AuditLogModel.performed_at < date_to)
        if cursor is not None:
            cursor_performed_at, cursor_id = _decode_cursor(cursor)
            # Keyset pagination via row-value comparison — strictly older
            # than the last-seen (performed_at, id), matching the
            # DESC/DESC ordering above.
            stmt = stmt.where(
                tuple_(AuditLogModel.performed_at, AuditLogModel.id)
                < tuple_(literal(cursor_performed_at), literal(cursor_id))
            )

        async for session in self._database.session(tenant_id=tenant_id):
            result = await session.execute(stmt)
            rows = list(result.scalars())
            has_next = len(rows) > limit
            page_rows = rows[:limit]

            next_cursor = (
                _encode_cursor(page_rows[-1].performed_at, page_rows[-1].id)
                if has_next and page_rows
                else None
            )
            return AuditLogPage(
                items=[self._to_domain(row) for row in page_rows], next_cursor=next_cursor
            )
        return AuditLogPage(items=[], next_cursor=None)  # pragma: no cover

    @staticmethod
    def _to_domain(row: AuditLogModel) -> AuditLogEntry:
        return AuditLogEntry(
            row.id,
            row.tenant_id,
            row.actor_id,
            row.entity_name,
            row.entity_id,
            row.action,
            row.performed_at,
            row.correlation_id,
            row.before_state,
            row.after_state,
        )
