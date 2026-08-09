"""The `Tenant` repository port.

Matches the shape `03-backend-architecture.md` §4 illustrates for
`OrderRepository` exactly: one repository per aggregate root, accepting and
returning the domain aggregate — never a partial DTO, never the SQLAlchemy
model. The implementation lives in
`lpg.infrastructure.persistence.repositories.tenant`.

No `add()` here. `tenant.tenant`'s RLS policy makes tenant creation
impossible through a tenant-scoped connection by design (see the migration
`0242df1a3871`'s docstring) — provisioning is a platform/admin operation,
out of Phase 2's scope, not a gap in this port.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from lpg.domain.tenant.tenant import Tenant


@runtime_checkable
class TenantRepository(Protocol):
    async def get(self, tenant_id: uuid.UUID) -> Tenant | None: ...

    async def save(self, tenant: Tenant) -> None: ...
