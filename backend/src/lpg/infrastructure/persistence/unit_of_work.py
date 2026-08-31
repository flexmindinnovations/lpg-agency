"""The concrete ``UnitOfWork`` (``lpg.application.common.ports.UnitOfWork``).

One instance per command, wrapping exactly one database transaction
(``03-backend-architecture.md`` §4). On a clean exit it commits; on an
exception it rolls back — both also callable explicitly, since a use case
that wants to be plain about what just happened (``await uow.commit()``) is
clearer than relying on context-manager magic alone. Whichever comes first
wins; the other is then a no-op, so a use case can call ``commit()``
explicitly and still use ``async with`` without double-committing.

Audit-row writing (step 2 of commit, per ``06-database-architecture.md`` §6)
is delegated to ``AuditRecorder`` (``lpg.infrastructure.persistence.audit``),
registered as a ``before_flush`` session event at construction — it fires
automatically inside ``session.flush()`` below, so this class does not call
it explicitly. Domain-event dispatch (step 4) delegates to a
``DomainEventDispatcher`` (``lpg.infrastructure.events.dispatcher``), passed
in at construction — optional, so callers/tests that only care about the
transaction boundary are unaffected.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from lpg.config.logging import get_logger
from lpg.infrastructure.persistence.audit import AuditRecorder

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from lpg.application.common.ports import TenantContext
    from lpg.domain.common.base import AggregateRoot, DomainEvent
    from lpg.infrastructure.events.dispatcher import DomainEventDispatcher

_logger = get_logger(__name__)


class SqlAlchemyUnitOfWork:
    """Owns one transaction, one set of touched aggregates, one dispatch."""

    def __init__(
        self,
        session: AsyncSession,
        tenant_context: TenantContext,
        *,
        event_dispatcher: DomainEventDispatcher | None = None,
    ) -> None:
        self._session = session
        self._tenant_context = tenant_context
        self._event_dispatcher = event_dispatcher
        self._tracked_aggregates: list[AggregateRoot] = []
        self._finished = False
        # Correlation ID travels via structlog's contextvars, already bound
        # for the request by CorrelationIdMiddleware — reading it here avoids
        # threading it through every constructor between the router and this
        # class (`12-observability.md` §4).
        correlation_id = structlog.contextvars.get_contextvars().get("correlation_id")
        self._audit_recorder = AuditRecorder(session, tenant_context, correlation_id=correlation_id)

    @property
    def session(self) -> AsyncSession:
        """The scoped session, for repository construction.

        Per ``03-backend-architecture.md`` §3.1, there is no repository
        constructor that takes a raw engine — repositories are always built
        from a session that already came through the tenant-scoping seam,
        and this is the only place that session is exposed.
        """
        return self._session

    def register_aggregate(self, aggregate: AggregateRoot) -> None:
        """Track an aggregate touched in this transaction.

        Called by repository implementations when they load or add an
        aggregate — never by application or domain code, which have no
        business knowing a Unit of Work exists (``03-backend-architecture.md``
        §5: application code receives collaborators as constructor arguments,
        it does not reach for a global).

        Idempotent by object identity: a use case that loads an aggregate
        (``get_by_id`` registers it) and then ``save``s it (registers again)
        must not have that aggregate's events collected — and dispatched —
        twice.
        """
        if any(tracked is aggregate for tracked in self._tracked_aggregates):
            return
        self._tracked_aggregates.append(aggregate)

    def collect_events(self) -> Sequence[DomainEvent]:
        """Events recorded by every aggregate touched in this transaction."""
        events: list[DomainEvent] = []
        for aggregate in self._tracked_aggregates:
            events.extend(aggregate.events)
        return tuple(events)

    async def commit(self) -> None:
        """Flush (triggering audit-row capture), commit, dispatch events.

        Idempotent after the first call. Event dispatch happens **after**
        ``session.commit()`` succeeds — a subscriber must never observe state
        a rollback would later have erased (``03-backend-architecture.md``
        §6) — and only once the transaction is durably finished, so a
        dispatch failure cannot be mistaken for a reason to roll back work
        that has already been committed.
        """
        if self._finished:
            return
        await self._session.flush()
        await self._session.commit()
        self._finished = True
        _logger.debug("unit_of_work_committed", tracked_aggregates=len(self._tracked_aggregates))

        if self._event_dispatcher is not None:
            events = self.collect_events()
            if events:
                await self._event_dispatcher.dispatch(events)
            for aggregate in self._tracked_aggregates:
                aggregate.clear_events()

    async def rollback(self) -> None:
        """Discard the transaction. Idempotent after the first call."""
        if self._finished:
            return
        await self._session.rollback()
        self._finished = True
        _logger.debug("unit_of_work_rolled_back")

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        """Signature matches the ``UnitOfWork`` protocol's ``*exc_info: object``
        exactly (rather than the three specifically-typed positional
        parameters Python's context-manager convention normally uses), since a
        narrower signature is not structurally compatible with the protocol
        under ``mypy --strict`` — a subtype's method must accept everything
        the protocol's callers might pass, not merely what this class expects
        to receive in practice.
        """
        if self._finished:
            return
        exc_type = exc_info[0] if exc_info else None
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()
