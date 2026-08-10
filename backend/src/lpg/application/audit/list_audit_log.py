"""`ListAuditLogUseCase` — the first read path `audit.audit_log` has had
since Phase 2 created it as write-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

    from lpg.application.audit.ports import AuditLogPage, AuditLogRepository


@dataclass(frozen=True, slots=True)
class ListAuditLogQuery:
    tenant_id: uuid.UUID
    entity_name: str | None = None
    actor_id: uuid.UUID | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    cursor: str | None = None
    limit: int = 50


class ListAuditLogUseCase:
    def __init__(self, repository: AuditLogRepository) -> None:
        self._repository = repository

    async def execute(self, query: ListAuditLogQuery) -> AuditLogPage:
        return await self._repository.get_page(
            query.tenant_id,
            entity_name=query.entity_name,
            actor_id=query.actor_id,
            date_from=query.date_from,
            date_to=query.date_to,
            cursor=query.cursor,
            limit=query.limit,
        )
