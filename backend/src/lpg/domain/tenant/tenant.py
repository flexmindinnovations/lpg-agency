"""The `Tenant` aggregate — Phase 2's Repository/CQRS/Domain-Event example.

**Not a Tenant Administration feature.** This exists to give Phase 2's
architectural proof (Repository pattern, Unit of Work, CQRS, domain events)
something real to persist, matching the `tenant.tenant` table introduced for
the RLS proof (Area O). There is no create/delete use case, no admin API — a
tenant's own name is the only thing this phase lets it change, and even that
exists to exercise the seam end-to-end, not because tenant self-service is a
Phase 2 requirement.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.domain.common.base import AggregateRoot, DomainEvent, InvariantViolation

if TYPE_CHECKING:
    import uuid


@dataclass(frozen=True, slots=True)
class TenantRenamed(DomainEvent):
    """Recorded when a tenant's display name changes.

    An illustrative event, not a real business notification — nothing
    subscribes to this in Phase 2. It exists to prove aggregates record
    events and the Unit of Work dispatches them post-commit (`03-backend
    -architecture.md` §6), the mechanism every real business event will use.
    """

    tenant_id: uuid.UUID | None = None
    new_name: str = ""


class Tenant(AggregateRoot):
    """The tenant registry root. See module docstring for scope."""

    __slots__ = ("_name", "_slug")

    def __init__(self, tenant_id: uuid.UUID, name: str, slug: str, *, version: int = 1) -> None:
        super().__init__(tenant_id, version=version)
        self._name = name
        self._slug = slug

    @property
    def name(self) -> str:
        return self._name

    @property
    def slug(self) -> str:
        return self._slug

    def rename(self, new_name: str) -> None:
        """Change the tenant's display name.

        The one behaviour this aggregate has, deliberately — enough to prove
        a domain method enforcing an invariant, mutating state, and recording
        an event, without building out anything resembling tenant
        administration.
        """
        stripped = new_name.strip()
        if not stripped:
            msg = "Tenant name cannot be empty."
            raise InvariantViolation(msg, tenant_id=str(self.id))

        self._name = stripped
        self.record_event(TenantRenamed(tenant_id=self.id, new_name=stripped))
