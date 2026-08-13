"""`audit` bounded-context ports — a **read-only** repository over
`audit.audit_log` (Phase 2, write-only until now).

`AuditLogEntry` is a plain read-model dataclass, not a domain aggregate — an
audit row has no behavior or invariants to enforce (it is an immutable
historical fact by construction, DB-enforced via `REVOKE UPDATE, DELETE`),
so hydrating a full `AggregateRoot` for it would be the "complicated CQRS
framework" `common/cqrs.py`'s own docstring rules out. Matches that
docstring's guidance that queries "bypass repositories entirely and read
through optimized paths" more literally than Phase 7's other list use
cases do, since there is genuinely no aggregate here to protect.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence
    from datetime import datetime


@dataclass(frozen=True, slots=True)
class AuditLogEntry:
    id: uuid.UUID
    tenant_id: uuid.UUID | None
    actor_id: uuid.UUID | None
    entity_name: str
    entity_id: str | None
    action: str
    performed_at: datetime
    correlation_id: str | None
    before_state: dict[str, Any] | None
    after_state: dict[str, Any] | None
    actor_display_name: str | None = None
    entity_display_name: str | None = None


@dataclass(frozen=True, slots=True)
class AuditLogPage:
    items: Sequence[AuditLogEntry]
    #: Opaque — pass back verbatim as `cursor` to fetch the next page.
    #: `None` means this is the last page.
    next_cursor: str | None


@runtime_checkable
class AuditLogRepository(Protocol):
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
        """Most-recent-first, keyset-paginated on `(performed_at, id)` —
        `10-api-design-guidelines.md` §4's cursor-based convention for
        high-volume append-only history, avoiding deep-offset's performance
        cliff.
        """
        ...
