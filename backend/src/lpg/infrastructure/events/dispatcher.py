"""In-process domain-event dispatcher (`03-backend-architecture.md` §6).

Handlers subscribe by event type. Dispatch is synchronous, in-process, and
happens **after** a successful commit — never before, so a subscriber can
never observe state a rollback then erases. `SqlAlchemyUnitOfWork.commit()`
is the only caller in this phase.

**No handler is registered anywhere in Phase 2.** This is infrastructure for
future modules — the first real handler registration arrives with the first
real cross-cutting reaction to a domain event (a notification, a read-model
projection), not before.

Documented seam, unchanged from Phase 1's architecture: if cross-module
messaging later needs durability (retry, ordering across restarts), this
dispatcher is replaced by a transactional outbox relayed by the background
worker — nothing in application or domain code changes when that happens,
because they only ever see `UnitOfWork.commit()`, never this class.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from lpg.config.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from lpg.domain.common.base import DomainEvent

    EventHandler = Callable[[DomainEvent], Awaitable[None]]

_logger = get_logger(__name__)


class DomainEventDispatcher:
    """Owns the handler registry and performs dispatch."""

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[EventHandler]] = defaultdict(list)

    def register(self, event_type: type[DomainEvent], handler: EventHandler) -> None:
        """Subscribe ``handler`` to every event of exactly ``event_type``.

        No subtype matching — an event type registers its own handlers only,
        keeping dispatch behaviour unambiguous as the event hierarchy grows.
        """
        self._handlers[event_type].append(handler)

    async def dispatch(self, events: Sequence[DomainEvent]) -> None:
        """Invoke every registered handler for each event, in order.

        A handler that raises is logged and re-raised — silently swallowing a
        post-commit handler failure would hide exactly the kind of bug this
        phase's `03-backend-architecture.md` §11 rule ("exceptions are never
        silently swallowed") exists to prevent. The transaction itself is
        already committed by this point; a failed handler cannot roll it
        back, which is the documented trade-off of synchronous in-process
        dispatch (§6's "documented seam" above).
        """
        for event in events:
            handlers = self._handlers.get(type(event), [])
            for handler in handlers:
                try:
                    await handler(event)
                except Exception:
                    _logger.exception(
                        "domain_event_handler_failed",
                        event_name=event.event_name,
                        event_id=str(event.event_id),
                    )
                    raise
