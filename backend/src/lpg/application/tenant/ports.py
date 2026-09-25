"""The `Tenant` repository port.

Matches the shape `03-backend-architecture.md` §4 illustrates for
`OrderRepository` exactly: one repository per aggregate root, accepting and
returning the domain aggregate — never a partial DTO, never the SQLAlchemy
model. The implementation lives in
`lpg.infrastructure.persistence.repositories.tenant`.

`add()` exists for the Platform Console only (Agency Provisioning, Phase 30).
`tenant.tenant`'s RLS policy makes tenant creation impossible through a
tenant-scoped connection by design (migration `0242df1a3871`'s docstring), so
it is backed by a `SECURITY DEFINER` function, never a plain INSERT.

`list_all()` is the one method here that is *never* callable through an
ordinary tenant-scoped session — `tenant.tenant`'s own RLS policy
(`id = current_setting('app.current_tenant_id')`) would return at most one
row, the caller's own. It exists for the Platform Console's Agency
Management page, backed by the `tenant.tenant_list_all()` `SECURITY
DEFINER` function (migration `fdd3afde337c`), called only through the
`/platform/*` dependency chain (`api/v1/dependencies/platform.py`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from lpg.domain.tenant.branch import Branch
    from lpg.domain.tenant.cylinder_type import CylinderType
    from lpg.domain.tenant.price_list import PriceListEntry
    from lpg.domain.tenant.price_list_proposal import PriceListProposal
    from lpg.domain.tenant.tenant import Tenant
    from lpg.domain.tenant.tenant_configuration import TenantConfiguration
    from lpg.domain.tenant.warehouse import Warehouse


@runtime_checkable
class TenantRepository(Protocol):
    async def get(self, tenant_id: uuid.UUID) -> Tenant | None: ...

    async def get_by_slug(self, slug: str) -> Tenant | None: ...

    async def add(self, tenant: Tenant) -> None:
        """Insert a brand-new tenant. Platform-only: goes through the
        `tenant.tenant_provision()` `SECURITY DEFINER` function (migration
        `d5b9e3a7f1c4`), the one way past `tenant.tenant`'s RLS INSERT block.
        Raises `ConflictError` if the slug is already taken."""
        ...

    async def save(self, tenant: Tenant) -> None: ...

    async def list_all(self) -> Sequence[Tenant]: ...


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


@runtime_checkable
class PriceListProposalRepository(Protocol):
    """A real review queue, unlike `PriceListRepository` — `save()` updates
    a proposal's `status`/`reviewed_by`/`reviewed_at` in place."""

    def next_id(self) -> uuid.UUID: ...

    async def add_ignoring_conflicts(self, proposals: list[PriceListProposal]) -> int:
        """Bulk-insert; a proposal whose `(tenant_id, cylinder_type_id,
        customer_type, branch_id, effective_from)` already exists is
        silently skipped (`ON CONFLICT DO NOTHING`) — a re-run of the
        monthly fetch job is a no-op. Returns the number actually
        inserted."""
        ...

    async def get(self, proposal_id: uuid.UUID) -> PriceListProposal | None: ...

    async def list_pending_for_tenant(
        self, tenant_id: uuid.UUID
    ) -> Sequence[PriceListProposal]: ...

    async def save(self, proposal: PriceListProposal) -> None: ...
