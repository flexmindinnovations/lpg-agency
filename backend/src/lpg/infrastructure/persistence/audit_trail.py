"""`SqlAlchemyPlatformAuditTrail` - explicit audit entries for Super Admin actions.

The generic audit hook (`persistence/audit.py`) only sees ORM changes made through
a Unit of Work's own session. Platform actions on an agency's users go through
repositories that open their own sessions (`SqlAlchemyStaffUserRepository`,
`SqlAlchemyPasswordResetTokenRepository`), so they would otherwise leave no
trace. This writes the entry by hand, in the platform Unit of Work that is
already scoped to the target agency: the row is attributed to that agency (so its
own admins see it in their audit log) with the Super Admin as the actor.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from lpg.infrastructure.persistence.models.audit_log import AuditLogModel

if TYPE_CHECKING:
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyPlatformAuditTrail:
    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    async def record(
        self,
        *,
        action: str,
        entity_name: str,
        entity_id: str,
        entity_display_name: str | None,
        details: dict[str, object],
    ) -> None:
        context = self._uow.tenant_context
        self._uow.session.add(
            AuditLogModel(
                tenant_id=context.tenant_id,
                actor_id=context.user_id,
                entity_name=entity_name,
                entity_id=entity_id,
                entity_display_name=entity_display_name,
                action=action,
                performed_at=datetime.now(UTC),
                correlation_id=structlog.contextvars.get_contextvars().get("correlation_id"),
                before_state=None,
                after_state=None,
                audit_metadata=details,
            )
        )
