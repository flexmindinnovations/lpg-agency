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
    from collections.abc import Sequence

    from lpg.domain.tenant.branch import Branch
    from lpg.domain.tenant.cylinder_type import CylinderType
    from lpg.domain.tenant.price_list import PriceListEntry
    from lpg.domain.tenant.tenant import Tenant
    from lpg.domain.tenant.tenant_configuration import TenantConfiguration
    from lpg.domain.tenant.warehouse import Warehouse


@runtime_checkable
class TenantRepository(Protocol):
    async def get(self, tenant_id: uuid.UUID) -> Tenant | None: ...

    async def save(self, tenant: Tenant) -> None: ...


@runtime_checkable
class BranchRepository(Protocol):
    async def get(self, branch_id: uuid.UUID) -> Branch | None: ...

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> Sequence[Branch]: ...

    async def add(self, branch: Branch) -> None: ...

    async def save(self, branch: Branch) -> None: ...


@runtime_checkable
class WarehouseRepository(Protocol):
    async def get(self, warehouse_id: uuid.UUID) -> Warehouse | None: ...

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> Sequence[Warehouse]: ...

    async def add(self, warehouse: Warehouse) -> None: ...

    async def save(self, warehouse: Warehouse) -> None: ...


@runtime_checkable
class CylinderTypeRepository(Protocol):
    async def get(self, cylinder_type_id: uuid.UUID) -> CylinderType | None: ...

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> Sequence[CylinderType]: ...

    async def add(self, cylinder_type: CylinderType) -> None: ...

    async def save(self, cylinder_type: CylinderType) -> None: ...


@runtime_checkable
class TenantConfigurationRepository(Protocol):
    """Append-only — no `get`/`save`, matching the table's own
    SELECT/INSERT-only grant (see migration `e5a1c7d3f9b2`).
    """

    async def list_for_tenant_and_key(
        self, tenant_id: uuid.UUID, config_key: str
    ) -> Sequence[TenantConfiguration]: ...

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> Sequence[TenantConfiguration]: ...

    async def add(self, config: TenantConfiguration) -> None: ...


@runtime_checkable
class PriceListRepository(Protocol):
    """Append-only — no `get`/`save`, same shape as
    `TenantConfigurationRepository`.
    """

    async def list_for_tenant_and_cylinder_type(
        self, tenant_id: uuid.UUID, cylinder_type_id: uuid.UUID, customer_type: str
    ) -> Sequence[PriceListEntry]: ...

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> Sequence[PriceListEntry]: ...

    async def add(self, entry: PriceListEntry) -> None: ...
