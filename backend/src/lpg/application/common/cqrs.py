"""Lightweight CQRS marker types (ADR-014; `03-backend-architecture.md` §2).

No mediator, no dispatch registry, no decorator-driven handler discovery.
A `Command` or `Query` is a plain, explicit dataclass; the use case that
handles it is a plain, explicit class with an `execute` method, called
directly by a thin router. These base classes exist only to make the
distinction readable at a glance across the codebase — "this type mutates
state" versus "this type reads state" — not to add behaviour.

Commands mutate through aggregates, loaded and saved via a repository, inside
a `UnitOfWork`. Queries bypass repositories entirely and read through
optimized paths (SQLAlchemy Core, views) — they have no invariants to
protect, so paying aggregate-hydration cost for them is waste. No query
example ships in Phase 2: there is no read model yet worth optimizing for,
and inventing one would be exactly the "complicated CQRS framework" the
Phase 2 instructions rule out.
"""

from __future__ import annotations


class Command:
    """Marker base for a request that mutates state.

    Subclasses are plain (usually frozen) dataclasses carrying only the data
    a use case needs — no behaviour, no framework dependency.
    """


class Query:
    """Marker base for a request that reads state, unchanged by handling."""
