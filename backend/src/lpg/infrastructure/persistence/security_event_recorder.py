"""`SqlAlchemySecurityEventRecorder` - logs and persists sign-in events.

Opens its own short transaction (sign-in has no Unit of Work, see
`application/identity/login.py`). An event with no known tenant (an unknown
email, say) is written under the platform sentinel tenant, which only the
Platform Console can read (migration 63c55035ebbb). Failures to persist are
logged and swallowed: auditing must never turn a sign-in into a 500.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from lpg.application.audit.security_events import ENTITY_NAME, SecurityEvent
from lpg.config.logging import get_logger
from lpg.infrastructure.persistence.models.audit_log import AuditLogModel

if TYPE_CHECKING:
    from lpg.infrastructure.persistence.database import Database

_logger = get_logger(__name__)

PLATFORM_SENTINEL_TENANT_ID = uuid.UUID(int=0)


class SqlAlchemySecurityEventRecorder:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def record(self, event: SecurityEvent) -> None:
        context = structlog.contextvars.get_contextvars()
        client_ip = context.get("client_ip")
        user_agent = context.get("user_agent")
        correlation_id = context.get("correlation_id")

        # The structured log line comes first and never depends on the database.
        log = _logger.info if event.outcome == "success" else _logger.warning
        log(
            "security_event",
            action=event.action,
            outcome=event.outcome,
            audit_tenant_id=str(event.tenant_id) if event.tenant_id else None,
            audit_user_id=str(event.user_id) if event.user_id else None,
            subject=event.subject,
            reason=event.reason,
            client_ip=client_ip,
        )

        if not event.persist:
            return

        details: dict[str, object] = {
            "outcome": event.outcome,
            "client_ip": client_ip,
            "user_agent": user_agent,
            **event.extra,
        }
        if event.subject:
            details["subject"] = event.subject
        if event.reason:
            details["reason"] = event.reason

        try:
            tenant_id = event.tenant_id or PLATFORM_SENTINEL_TENANT_ID
            async for session in self._database.session(
                tenant_id=event.tenant_id  # None -> unscoped session (platform rows)
            ):
                session.add(
                    AuditLogModel(
                        tenant_id=tenant_id,
                        actor_id=event.user_id,
                        actor_display_name=event.subject,
                        entity_name=ENTITY_NAME,
                        entity_id=str(event.user_id) if event.user_id else None,
                        entity_display_name=event.subject,
                        action=event.action,
                        performed_at=datetime.now(UTC),
                        correlation_id=str(correlation_id) if correlation_id else None,
                        # `after_state` is what the Audit Log page's Details table
                        # shows; `metadata` keeps the same facts for queries.
                        after_state=details,
                        audit_metadata=details,
                    )
                )
        except Exception:
            _logger.exception("security_event_persist_failed", action=event.action)
