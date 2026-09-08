"""Repository ports for the `compliance` bounded context (Weighment Part 1,
TDT rating Part 2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

    from lpg.domain.compliance.cylinder_unit import CylinderUnit
    from lpg.domain.compliance.scale import Scale
    from lpg.domain.compliance.weighment_record import WeighmentRecord


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


class WeighmentRecordRepository(Protocol):
    """Persistence for `WeighmentRecord` — tenant-scoped by RLS on
    `compliance.weighment_record`. Append-only: no `save`-then-mutate,
    just `add`."""

    def next_id(self) -> uuid.UUID: ...

    async def add(self, record: WeighmentRecord) -> None: ...

    async def list_for_reference(
        self, reference_type: str, reference_id: uuid.UUID
    ) -> list[WeighmentRecord]: ...

    async def get_latest_passing_for_reference(
        self, reference_type: str, reference_id: uuid.UUID, *, context: str
    ) -> WeighmentRecord | None:
        """The most recent `result = 'pass'` record for this reference and
        context, if any — what Part 3's load-out gate checks for."""
        ...


class CylinderUnitRepository(Protocol):
    """Persistence for `CylinderUnit` — tenant-scoped by RLS on
    `compliance.cylinder_unit`."""

    def next_id(self) -> uuid.UUID: ...

    async def save(self, unit: CylinderUnit) -> None: ...

    async def get_by_id(self, unit_id: uuid.UUID) -> CylinderUnit | None: ...

    async def get_by_serial(self, serial_number: str) -> CylinderUnit | None: ...

    async def get_by_qr_code(self, qr_code: str) -> CylinderUnit | None: ...

    async def lookup_by_code(self, code: str) -> CylinderUnit | None: ...

    async def list_for_tenant(
        self,
        *,
        due_status: str | None = None,
        cylinder_type_id: uuid.UUID | None = None,
        custody_type: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[CylinderUnit]:
        """Registry list — `due_status` is `due_soon` (<=30 days) or
        `overdue`, same `expiry`-filter idiom `ScaleRepository.list_for_
        tenant` already establishes. Excludes retired units unless a
        future need for them arises — not exposed as a filter yet."""
        ...

    async def count_for_tenant(
        self,
        *,
        due_status: str | None = None,
        cylinder_type_id: uuid.UUID | None = None,
        custody_type: str | None = None,
    ) -> int: ...


@dataclass(frozen=True, slots=True)
class OrderFulfillmentRecord:
    """One delivered order's booking-to-delivery span, for TDT rating
    (Phase 20 subsystem 2). `booked_at`/`delivered_at` are pivoted out of
    `orders.order_status_history`'s `to_status` transitions."""

    order_id: uuid.UUID
    branch_id: uuid.UUID
    booked_at: datetime
    delivered_at: datetime


class TdtRatingRepository(Protocol):
    """Reads `orders.order_status_history` joined to `orders.order` for TDT
    rating. `order_status_history` carries **no `tenant_id` column and no
    Row-Level Security policy of its own** (it's excluded from RLS, same
    precedent as `inventory.inventory_transaction` — see the orders-schema
    migration's own comment) — tenant isolation here comes entirely from
    the join to `orders.order`, which *is* RLS-protected, the same way
    every other repository in this codebase relies on the session's
    `app.current_tenant_id` context rather than an explicit `tenant_id`
    parameter. This is exactly why TDT rating needs its own dedicated
    cross-tenant-isolation test rather than trusting the RLS suite alone.
    """

    async def get_fulfillment_records(
        self,
        quarter_start: datetime,
        quarter_end: datetime,
        *,
        branch_id: uuid.UUID | None = None,
    ) -> list[OrderFulfillmentRecord]:
        """Every order whose `booked` transition falls within
        `[quarter_start, quarter_end)` **and** has since reached
        `delivered` — an order still in flight or cancelled within the
        window is excluded from this pass (an open policy question — see
        `SqlAlchemyTdtRatingRepository.get_fulfillment_records`'s own
        docstring and the source plan's open questions)."""
        ...
