"""Repository ports for the inventory bounded context.

`InventoryLocationRepository` is the sole aggregate repository. GRN and
reconciliation records are entities of that aggregate conceptually but are
append-only/two-step records with no in-memory collection to load-and-mutate
(`docs/data/01-domain-model.md` §4.6/§7), so their repositories are thin
insert/get ports returning plain read-model dataclasses, not domain objects
— the same reasoning `application/audit/ports.py` already documents for why
`AuditLogEntry` isn't a hydrated aggregate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence
    from datetime import datetime

    from lpg.domain.inventory.inventory_location import InventoryLocation


@dataclass(frozen=True, slots=True)
class InventoryTransactionEntry:
    id: uuid.UUID
    tenant_id: uuid.UUID
    inventory_location_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    transaction_type: str
    from_status: str | None
    to_status: str
    quantity: int
    reference_order_id: uuid.UUID | None
    reason: str | None
    performed_by: uuid.UUID
    performed_at: datetime


@dataclass(frozen=True, slots=True)
class InventoryTransactionPage:
    items: Sequence[InventoryTransactionEntry]
    #: Opaque — pass back verbatim as `cursor` to fetch the next page.
    #: `None` means this is the last page.
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class GoodsReceiptNoteEntry:
    id: uuid.UUID
    tenant_id: uuid.UUID
    warehouse_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    quantity_received: int
    source_omc: str | None
    received_by: uuid.UUID
    received_at: datetime


@dataclass(frozen=True, slots=True)
class ReconciliationRecordEntry:
    id: uuid.UUID
    tenant_id: uuid.UUID
    inventory_location_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    status: str
    expected_quantity: int
    actual_quantity: int
    variance: int
    recorded_by: uuid.UUID
    approved_by: uuid.UUID | None
    approved_at: datetime | None


class InventoryLocationRepository(Protocol):
    def next_id(self) -> uuid.UUID: ...

    async def save(self, location: InventoryLocation) -> None: ...

    async def get_by_id(self, location_id: uuid.UUID) -> InventoryLocation | None: ...

    async def get_by_location_ref(
        self, location_type: str, location_ref_id: uuid.UUID
    ) -> InventoryLocation | None:
        """Looked up for lazy create-on-first-use — no row exists until the
        first mutating operation against a given warehouse/vehicle.
        """
        ...

    async def list_transactions(
        self,
        location_id: uuid.UUID,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> InventoryTransactionPage:
        """Most-recent-first, keyset-paginated on `(performed_at, id)` —
        `10-api-design-guidelines.md` §4's cursor-based convention for a
        high-volume append-only history.
        """
        ...

    async def get_balance_summary(self) -> dict[str, int]:
        """Total quantity grouped by status, across every location the
        tenant has — a platform-wide reporting figure, not a single
        aggregate's state, so this reads the materialized projection
        directly rather than hydrating every `InventoryLocation`.
        """
        ...


class GoodsReceiptNoteRepository(Protocol):
    def next_id(self) -> uuid.UUID: ...

    async def create(
        self,
        *,
        grn_id: uuid.UUID,
        tenant_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        cylinder_type_id: uuid.UUID,
        quantity_received: int,
        source_omc: str | None,
        received_by: uuid.UUID,
    ) -> GoodsReceiptNoteEntry: ...


class ReconciliationRecordRepository(Protocol):
    def next_id(self) -> uuid.UUID: ...

    async def create(
        self,
        *,
        record_id: uuid.UUID,
        tenant_id: uuid.UUID,
        inventory_location_id: uuid.UUID,
        cylinder_type_id: uuid.UUID,
        status: str,
        expected_quantity: int,
        actual_quantity: int,
        recorded_by: uuid.UUID,
    ) -> ReconciliationRecordEntry: ...

    async def get_by_id(self, record_id: uuid.UUID) -> ReconciliationRecordEntry | None: ...

    async def get_latest_for_location(
        self, inventory_location_id: uuid.UUID
    ) -> ReconciliationRecordEntry | None:
        """Most recently created record for this location, regardless of
        `cylinder_type_id`/`status`. Used by `CompleteRouteReconciliationUseCase`
        as a simplified "has this vehicle been reconciled at all" gate —
        a real per-cylinder-type-and-status completeness check is future
        scope, not built here.
        """
        ...

    async def approve(
        self, record_id: uuid.UUID, *, approved_by: uuid.UUID
    ) -> ReconciliationRecordEntry: ...
