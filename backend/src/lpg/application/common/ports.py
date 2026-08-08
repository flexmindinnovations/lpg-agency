"""Application layer ports.

Ports are ``Protocol`` classes the application layer defines and the
infrastructure layer implements — dependency inversion. Application code
depends on the protocol, never the implementation, which is what makes use
cases unit-testable with in-memory fakes and no database.

Phase 1 defines the foundation ports only. Repository protocols arrive with
their aggregates, one per aggregate root, in their own phases.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from lpg.domain.common.base import DomainEvent


@runtime_checkable
class UnitOfWork(Protocol):
    """The transaction boundary for a single command.

    Entered once per command. On commit it flushes changes, writes audit rows
    from captured before/after state (BR-28), commits, and only then dispatches
    domain events.

    This is what guarantees BR-29: a delivery confirmation updates Order,
    Cylinder Ledger and Inventory in one transaction, or none of them.
    """

    async def __aenter__(self) -> UnitOfWork: ...

    async def __aexit__(self, *exc_info: object) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...

    def collect_events(self) -> Sequence[DomainEvent]:
        """Return events recorded by every aggregate touched in this transaction."""
        ...


@runtime_checkable
class TenantContext(Protocol):
    """The tenant and actor a request executes on behalf of.

    Every request runs inside one of these. Resolved from the verified JWT
    claim, never from a client-supplied header or body parameter — that would
    make tenant spoofing a single request away (ADR-017).
    """

    @property
    def tenant_id(self) -> uuid.UUID: ...

    @property
    def user_id(self) -> uuid.UUID | None: ...


@runtime_checkable
class RealtimePublisher(Protocol):
    """Transport-agnostic publication of real-time messages.

    Domain and application code import only this protocol. The Redis Pub/Sub
    implementation lives in infrastructure, so swapping the transport — to SSE,
    to a managed service, to a broker — touches one module and nothing else
    (ADR-015, ``16-realtime-architecture.md`` §3.2).

    Not wired to any publisher in Phase 1; the port exists so later phases have
    a stable seam to build against.
    """

    async def publish(self, channel: str, message: dict[str, Any]) -> None: ...


@runtime_checkable
class CacheClient(Protocol):
    """Key/value cache access.

    Keys are tenant-scoped by convention (``tenant:{id}:...``) so a cache entry
    can never be served across a tenant boundary.
    """

    async def get(self, key: str) -> str | None: ...

    async def set(self, key: str, value: str, *, ttl_seconds: int | None = None) -> None: ...

    async def delete(self, key: str) -> None: ...


@runtime_checkable
class HealthCheck(Protocol):
    """A dependency that can report whether it is reachable.

    Used by the readiness endpoint. Liveness deliberately checks nothing —
    see ``lpg.api.v1.routers.health``.
    """

    @property
    def name(self) -> str: ...

    async def check(self) -> bool: ...
