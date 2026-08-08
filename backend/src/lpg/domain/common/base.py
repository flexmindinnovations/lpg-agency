"""Domain layer base classes.

The domain layer has **zero outward dependencies** — no FastAPI, no
SQLAlchemy, no Pydantic-for-persistence. Plain Python only. This is enforced
in CI by ``import-linter`` contracts (ADR-024), not by convention.

Only base classes live here. **No business aggregate is defined in Phase 1.**
Customer, Order, Inventory, Delivery, Ledger, Invoice and the rest arrive in
their own phases, each with its own plan.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Something that happened in the domain, expressed in the past tense.

    Events are immutable. Aggregates *record* them; the Unit of Work dispatches
    them **after** a successful commit, so a subscriber never observes state
    that a rollback then erases (``03-backend-architecture.md`` §6).
    """

    event_id: uuid.UUID = field(default_factory=uuid.uuid4, kw_only=True)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC), kw_only=True)

    @property
    def event_name(self) -> str:
        return type(self).__name__


class ValueObject:
    """A domain concept defined by its attributes rather than an identity.

    Value objects are immutable and compared by value. Subclasses should be
    declared as ``@dataclass(frozen=True)``.
    """

    __slots__ = ()


class Entity:
    """A domain object with a stable identity that persists across changes.

    Two entities are the same entity when their identifiers match, regardless
    of whether any other attribute differs.
    """

    __slots__ = ("_id",)

    def __init__(self, entity_id: uuid.UUID) -> None:
        self._id = entity_id

    @property
    def id(self) -> uuid.UUID:
        return self._id

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return type(self) is type(other) and self._id == other._id

    def __hash__(self) -> int:
        return hash((type(self).__name__, self._id))

    def __repr__(self) -> str:
        return f"{type(self).__name__}(id={self._id})"


class AggregateRoot(Entity):
    """The single entry point to an aggregate.

    External code interacts with an aggregate only through its root. Invariants
    are enforced here, unconditionally — an aggregate must be impossible to put
    into an invalid state even when reached from a code path that skipped
    request validation. That is precisely why domain invariants are not
    implemented as request validators (``03-backend-architecture.md`` §9).

    Version supports optimistic concurrency (``version_id_col`` at the ORM
    layer). It matters most for the offline-first Driver App, where a stale
    local copy may try to overwrite newer server state — the version check
    turns that into a resolvable conflict rather than silent data loss.
    """

    __slots__ = ("_events", "_version")

    def __init__(self, entity_id: uuid.UUID, *, version: int = 1) -> None:
        super().__init__(entity_id)
        self._version = version
        self._events: list[DomainEvent] = []

    @property
    def version(self) -> int:
        return self._version

    @property
    def events(self) -> tuple[DomainEvent, ...]:
        """Events recorded but not yet dispatched."""
        return tuple(self._events)

    def record_event(self, event: DomainEvent) -> None:
        """Record an event for dispatch after commit.

        Aggregates never publish directly. An aggregate that knows about a
        message bus is no longer framework-independent.
        """
        self._events.append(event)

    def clear_events(self) -> None:
        """Called by the Unit of Work once events have been dispatched."""
        self._events.clear()


class DomainError(Exception):
    """Base class for violations of a business rule.

    Distinct from infrastructure failures. These map to 4xx responses with a
    business-meaningful ``error_code`` (ADR-021); infrastructure failures map
    to 5xx and are never surfaced to the client in detail.
    """

    error_code: str = "DOMAIN_ERROR"

    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(message)
        self.message = message
        self.context = context


class BusinessRuleViolation(DomainError):
    """A specific, named business rule was violated."""

    error_code = "BUSINESS_RULE_VIOLATION"


class InvariantViolation(DomainError):
    """An aggregate invariant would be broken by the attempted operation.

    Distinct from ``BusinessRuleViolation``: this indicates the aggregate is
    protecting its own consistency (inventory cannot go negative, a ledger must
    balance), not that a configurable policy was breached.
    """

    error_code = "INVARIANT_VIOLATION"
