"""Repository ports for the `compliance` bounded context (Weighment Part 1)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid

    from lpg.domain.compliance.scale import Scale


class ScaleRepository(Protocol):
    """Persistence for `Scale` — tenant-scoped by RLS on `compliance.scale`."""

    def next_id(self) -> uuid.UUID: ...

    async def save(self, scale: Scale) -> None: ...

    async def get_by_id(self, scale_id: uuid.UUID) -> Scale | None: ...

    async def get_by_warehouse_and_asset_tag(
        self, warehouse_id: uuid.UUID, asset_tag: str
    ) -> Scale | None: ...

    async def list_for_warehouse(self, warehouse_id: uuid.UUID) -> list[Scale]: ...

    async def list_for_tenant(
        self,
        *,
        status: str | None = None,
        expiry: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Scale]:
        """Tenant-wide scale list for the registry page — `expiry` is
        `expiring` (<=30 days) or `expired`, same semantics as
        `ComplianceDocumentRepository.list_for_tenant`."""
        ...

    async def count_for_tenant(
        self,
        *,
        status: str | None = None,
        expiry: str | None = None,
    ) -> int: ...
