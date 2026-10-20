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

from sqlalchemy import Table, literal, select, tuple_

from lpg.application.audit.ports import AuditLogEntry, AuditLogPage
from lpg.infrastructure.persistence.audit_labels import (
    PARENT_COLUMNS,
    audit_label,
    parent_references,
)
from lpg.infrastructure.persistence.database import Base
from lpg.infrastructure.persistence.models.audit_log import AuditLogModel

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from typing import Any

    from sqlalchemy.ext.asyncio import AsyncSession

    from lpg.infrastructure.persistence.database import Database

_CURSOR_SEPARATOR = "|"


def _encode_cursor(performed_at: datetime, entry_id: uuid.UUID) -> str:
    return f"{performed_at.isoformat()}{_CURSOR_SEPARATOR}{entry_id}"


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    performed_at_iso, entry_id = cursor.rsplit(_CURSOR_SEPARATOR, 1)
    return datetime.fromisoformat(performed_at_iso), uuid.UUID(entry_id)


#: Parent tables a label may need — the only tables read-time labelling reads.
_LABEL_TABLES = frozenset(table for _, table in PARENT_COLUMNS)


def _tables_by_name() -> dict[str, Table]:
    tables: dict[str, Table] = {}
    for mapper in Base.registry.mappers:
        table = mapper.local_table
        if isinstance(table, Table) and table.name in _LABEL_TABLES:
            tables[table.name] = table
    return tables


def _row_values(row: AuditLogModel) -> Mapping[str, Any] | None:
    return row.after_state or row.before_state


class SqlAlchemyAuditLogRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def get_page(
        self,
        tenant_id: uuid.UUID,
        *,
        entity_name: str | None = None,
        actor_id: uuid.UUID | None = None,
        action: str | None = None,
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
        if action is not None:
            stmt = stmt.where(AuditLogModel.action == action)
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
            labels = await self._labels_for_unnamed(session, page_rows)
            return AuditLogPage(
                items=[self._to_domain(row, labels.get(row.id)) for row in page_rows],
                next_cursor=next_cursor,
            )
        return AuditLogPage(items=[], next_cursor=None)  # pragma: no cover

    async def list_entity_names(self, tenant_id: uuid.UUID) -> list[str]:
        """Every record type this tenant's audit log mentions, for the
        Audit Log's "Record type" filter."""
        stmt = (
            select(AuditLogModel.entity_name)
            .where(AuditLogModel.tenant_id == tenant_id)
            .distinct()
            .order_by(AuditLogModel.entity_name)
        )
        async for session in self._database.session(tenant_id=tenant_id):
            return list((await session.execute(stmt)).scalars())
        return []  # pragma: no cover

    async def _labels_for_unnamed(
        self, session: AsyncSession, rows: Iterable[AuditLogModel]
    ) -> dict[uuid.UUID, str]:
        """Labels for rows written without one (before labels existed, or
        whose parent was not loaded at write time), from their stored state
        and their parents — one query per parent table for the whole page.
        Runs in the tenant's RLS session, so a parent from another tenant is
        simply never found."""
        unnamed = [row for row in rows if not row.entity_display_name and _row_values(row)]
        if not unnamed:
            return {}
        tables = _tables_by_name()
        fetched: dict[tuple[str, str], Mapping[str, Any]] = {}
        pending = {ref for row in unnamed for ref in parent_references(_row_values(row))}
        # Two rounds: a route stop's route, then that route's vehicle.
        for _ in range(2):
            wanted = {ref for ref in pending if ref not in fetched and ref[0] in tables}
            if not wanted:
                break
            pending = set()
            for table_name in {table for table, _ in wanted}:
                ids = []
                for ref_table, raw_id in wanted:
                    if ref_table != table_name:
                        continue
                    try:
                        ids.append(uuid.UUID(raw_id))
                    except ValueError:
                        continue
                if not ids:
                    continue
                source = tables[table_name]
                result = await session.execute(select(source).where(source.c.id.in_(ids)))
                for record in result.mappings():
                    values = {key: record[key] for key in record}
                    fetched[(table_name, str(values["id"]))] = values
                    pending.update(parent_references(values))

        def lookup(table: str, entity_id: str) -> Mapping[str, Any] | None:
            return fetched.get((table, entity_id))

        labels: dict[uuid.UUID, str] = {}
        for row in unnamed:
            label = audit_label(row.entity_name, _row_values(row), lookup)
            if label:
                labels[row.id] = label
        return labels

    @staticmethod
    def _to_domain(row: AuditLogModel, fallback_label: str | None = None) -> AuditLogEntry:
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
            row.actor_display_name,
            row.entity_display_name or fallback_label,
        )
