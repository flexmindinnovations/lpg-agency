"""Application use cases for the inventory bounded context.

**Lazy create-on-first-use, applied uniformly**: every mutating command here
resolves its `InventoryLocation` via `GetOrCreateInventoryLocationUseCase`
(looked up by `(location_type, location_ref_id)` — a warehouse or vehicle
id, not an opaque `inventory_location_id`). A location with zero activity
has no persisted row and is never assigned an id a client could have
discovered; the aggregate is synthesized in memory with all-zero balances
and only gets a row once `save()` actually persists it (on the first
successful mutation). Read use cases (`GetInventoryBalanceUseCase`,
`ListInventoryTransactionsUseCase`) resolve the same way and *never* save —
a never-touched warehouse/vehicle legitimately returns an all-zero balance
or an empty transaction page, not 404. This is why no use case here accepts
a bare `inventory_location_id`: doing so would make a brand-new
warehouse/vehicle's inventory undiscoverable until some other endpoint
invented an id-lookup step the plan never called for.

Commands follow the established pattern: delegate all business invariant
checks to the aggregate, persist via the repository, commit via the Unit of
Work, which dispatches domain events after commit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command, Query
from lpg.application.common.errors import NotFoundError, ValidationError
from lpg.domain.inventory.inventory_location import (
    CYLINDER_STATUSES,
    OMC_CODES,
    InventoryLocation,
    signed_balance_changes,
)
from lpg.domain.inventory.reconciliation import ensure_reconciliation_decidable

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from lpg.application.common.ports import UnitOfWork
    from lpg.application.inventory.ports import (
        GoodsReceiptNoteEntry,
        GoodsReceiptNoteRepository,
        GrnNumberSequence,
        InventoryLocationRepository,
        InventoryTransactionPage,
        OmcReturnNoteEntry,
        OmcReturnNoteRepository,
        OmcReturnNumberSequence,
        ReconciliationRecordEntry,
        ReconciliationRecordRepository,
    )


# ==========================================================================
# Internal helper — not directly API-exposed
# ==========================================================================


class GetOrCreateInventoryLocationUseCase:
    def __init__(self, repository: InventoryLocationRepository) -> None:
        self._repository = repository

    async def execute(
        self, *, tenant_id: uuid.UUID, location_type: str, location_ref_id: uuid.UUID
    ) -> InventoryLocation:
        location = await self._repository.get_by_location_ref(location_type, location_ref_id)
        if location is not None:
            return location
        return InventoryLocation(
            inventory_location_id=self._repository.next_id(),
            tenant_id=tenant_id,
            location_type=location_type,
            location_ref_id=location_ref_id,
        )


# ==========================================================================
# Goods Receipt (D-15)
# ==========================================================================


@dataclass(frozen=True, slots=True)
class RecordGoodsReceiptCommand(Command):
    tenant_id: uuid.UUID
    warehouse_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    quantity_received: int
    received_by: uuid.UUID
    source_omc: str | None = None
    challan_number: str | None = None
    invoice_number: str | None = None
    truck_number: str | None = None


def _require_omc(code: str | None, *, field: str) -> str | None:
    """Accepts any casing (`IOCL`) and stores the canonical code (`iocl`);
    an unknown OMC is a 422 with the allowed list, never a database error."""
    if code is None or not code.strip():
        return None
    normalized = code.strip().lower()
    if normalized not in OMC_CODES:
        msg = f"Unknown OMC '{code}'. Choose one of: {', '.join(sorted(OMC_CODES)).upper()}."
        raise ValidationError(msg, field=field)
    return normalized


def _clean(text: str | None) -> str | None:
    """Trim a free-text document reference; blank means not given."""
    if text is None:
        return None
    stripped = " ".join(text.split())
    return stripped.upper() or None


class RecordGoodsReceiptUseCase:
    def __init__(
        self,
        location_repository: InventoryLocationRepository,
        grn_repository: GoodsReceiptNoteRepository,
        unit_of_work: UnitOfWork,
        grn_number_sequence: GrnNumberSequence,
    ) -> None:
        self._location_repository = location_repository
        self._grn_repository = grn_repository
        self._unit_of_work = unit_of_work
        self._grn_number_sequence = grn_number_sequence
        self._get_or_create = GetOrCreateInventoryLocationUseCase(location_repository)

    async def execute(self, command: RecordGoodsReceiptCommand) -> GoodsReceiptNoteEntry:
        source_omc = _require_omc(command.source_omc, field="source_omc")
        location = await self._get_or_create.execute(
            tenant_id=command.tenant_id,
            location_type="warehouse",
            location_ref_id=command.warehouse_id,
        )
        location.receive_goods(
            command.cylinder_type_id, command.quantity_received, performed_by=command.received_by
        )
        await self._location_repository.save(location)

        grn_number = await self._grn_number_sequence.next()
        grn = await self._grn_repository.create(
            grn_id=self._grn_repository.next_id(),
            tenant_id=command.tenant_id,
            warehouse_id=command.warehouse_id,
            cylinder_type_id=command.cylinder_type_id,
            quantity_received=command.quantity_received,
            source_omc=source_omc,
            received_by=command.received_by,
            grn_number=grn_number,
            challan_number=_clean(command.challan_number),
            invoice_number=_clean(command.invoice_number),
            truck_number=_clean(command.truck_number),
        )
        await self._unit_of_work.commit()
        return grn


# ==========================================================================
# Empties return to the OMC (outward counterpart of a GRN)
# ==========================================================================


@dataclass(frozen=True, slots=True)
class ReturnStockToOmcCommand(Command):
    tenant_id: uuid.UUID
    warehouse_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    quantity: int
    destination_omc: str
    dispatched_by: uuid.UUID
    #: `empty` for the refill cycle; a defective status for segregated
    #: cylinders going back to the plant.
    status: str = "empty"
    challan_number: str | None = None
    truck_number: str | None = None


class ReturnStockToOmcUseCase:
    """Debits the warehouse and records a numbered return note (ERN…) in one
    transaction — the challan the OMC's truck carries back to the plant."""

    def __init__(
        self,
        location_repository: InventoryLocationRepository,
        note_repository: OmcReturnNoteRepository,
        number_sequence: OmcReturnNumberSequence,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._location_repository = location_repository
        self._note_repository = note_repository
        self._number_sequence = number_sequence
        self._unit_of_work = unit_of_work
        self._get_or_create = GetOrCreateInventoryLocationUseCase(location_repository)

    async def execute(self, command: ReturnStockToOmcCommand) -> OmcReturnNoteEntry:
        destination_omc = _require_omc(command.destination_omc, field="destination_omc")
        if destination_omc is None:
            msg = "Choose the OMC the cylinders are going back to."
            raise ValidationError(msg, field="destination_omc")
        return_number = await self._number_sequence.next()
        location = await self._get_or_create.execute(
            tenant_id=command.tenant_id,
            location_type="warehouse",
            location_ref_id=command.warehouse_id,
        )
        location.return_to_omc(
            command.cylinder_type_id,
            command.status,
            command.quantity,
            performed_by=command.dispatched_by,
            reason=f"Return note {return_number}",
        )
        await self._location_repository.save(location)
        note = await self._note_repository.create(
            note_id=self._note_repository.next_id(),
            tenant_id=command.tenant_id,
            return_number=return_number,
            warehouse_id=command.warehouse_id,
            cylinder_type_id=command.cylinder_type_id,
            status=command.status,
            quantity=command.quantity,
            destination_omc=destination_omc,
            challan_number=_clean(command.challan_number),
            truck_number=_clean(command.truck_number),
            dispatched_by=command.dispatched_by,
        )
        await self._unit_of_work.commit()
        return note


# ==========================================================================
# Load transfer (warehouse -> vehicle)
# ==========================================================================


@dataclass(frozen=True, slots=True)
class LoadTransferLine:
    cylinder_type_id: uuid.UUID
    status: str
    quantity: int


@dataclass(frozen=True, slots=True)
class LoadTransferCommand(Command):
    tenant_id: uuid.UUID
    warehouse_id: uuid.UUID
    vehicle_id: uuid.UUID
    lines: Sequence[LoadTransferLine]
    performed_by: uuid.UUID


class LoadTransferUseCase:
    def __init__(self, repository: InventoryLocationRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work
        self._get_or_create = GetOrCreateInventoryLocationUseCase(repository)

    async def execute(
        self, command: LoadTransferCommand
    ) -> tuple[InventoryLocation, InventoryLocation]:
        warehouse_location = await self._get_or_create.execute(
            tenant_id=command.tenant_id,
            location_type="warehouse",
            location_ref_id=command.warehouse_id,
        )
        vehicle_location = await self._get_or_create.execute(
            tenant_id=command.tenant_id, location_type="vehicle", location_ref_id=command.vehicle_id
        )

        # All mutation happens in memory before either aggregate is saved —
        # if any line's unload() raises InsufficientStockError partway
        # through, nothing below has run and nothing is saved (BR-29: one
        # transaction or none).
        for line in command.lines:
            warehouse_location.unload(
                line.cylinder_type_id, line.status, line.quantity, performed_by=command.performed_by
            )
            vehicle_location.load(
                line.cylinder_type_id, line.status, line.quantity, performed_by=command.performed_by
            )

        await self._repository.save(warehouse_location)
        await self._repository.save(vehicle_location)
        await self._unit_of_work.commit()
        return warehouse_location, vehicle_location


# ==========================================================================
# Delivery / collection (vehicle-only)
# ==========================================================================


@dataclass(frozen=True, slots=True)
class RecordDeliveryCommand(Command):
    tenant_id: uuid.UUID
    vehicle_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    quantity: int
    performed_by: uuid.UUID


class RecordDeliveryUseCase:
    def __init__(self, repository: InventoryLocationRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work
        self._get_or_create = GetOrCreateInventoryLocationUseCase(repository)

    async def execute(self, command: RecordDeliveryCommand) -> InventoryLocation:
        location = await self._get_or_create.execute(
            tenant_id=command.tenant_id, location_type="vehicle", location_ref_id=command.vehicle_id
        )
        location.record_delivery(
            command.cylinder_type_id, command.quantity, performed_by=command.performed_by
        )
        await self._repository.save(location)
        await self._unit_of_work.commit()
        return location


@dataclass(frozen=True, slots=True)
class RecordCollectionCommand(Command):
    tenant_id: uuid.UUID
    vehicle_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    quantity: int
    performed_by: uuid.UUID


class RecordCollectionUseCase:
    def __init__(self, repository: InventoryLocationRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work
        self._get_or_create = GetOrCreateInventoryLocationUseCase(repository)

    async def execute(self, command: RecordCollectionCommand) -> InventoryLocation:
        location = await self._get_or_create.execute(
            tenant_id=command.tenant_id, location_type="vehicle", location_ref_id=command.vehicle_id
        )
        location.record_collection(
            command.cylinder_type_id, command.quantity, performed_by=command.performed_by
        )
        await self._repository.save(location)
        await self._unit_of_work.commit()
        return location


# ==========================================================================
# Status change / adjustment (warehouse or vehicle)
# ==========================================================================


@dataclass(frozen=True, slots=True)
class ChangeCylinderStatusCommand(Command):
    tenant_id: uuid.UUID
    location_type: str
    location_ref_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    from_status: str
    to_status: str
    quantity: int
    performed_by: uuid.UUID


class ChangeCylinderStatusUseCase:
    def __init__(self, repository: InventoryLocationRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work
        self._get_or_create = GetOrCreateInventoryLocationUseCase(repository)

    async def execute(self, command: ChangeCylinderStatusCommand) -> InventoryLocation:
        location = await self._get_or_create.execute(
            tenant_id=command.tenant_id,
            location_type=command.location_type,
            location_ref_id=command.location_ref_id,
        )
        location.change_status(
            command.cylinder_type_id,
            command.from_status,
            command.to_status,
            command.quantity,
            performed_by=command.performed_by,
        )
        await self._repository.save(location)
        await self._unit_of_work.commit()
        return location


@dataclass(frozen=True, slots=True)
class AdjustInventoryCommand(Command):
    tenant_id: uuid.UUID
    location_type: str
    location_ref_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    from_status: str
    to_status: str
    quantity: int
    performed_by: uuid.UUID
    reason: str


class AdjustInventoryUseCase:
    def __init__(self, repository: InventoryLocationRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work
        self._get_or_create = GetOrCreateInventoryLocationUseCase(repository)

    async def execute(self, command: AdjustInventoryCommand) -> InventoryLocation:
        location = await self._get_or_create.execute(
            tenant_id=command.tenant_id,
            location_type=command.location_type,
            location_ref_id=command.location_ref_id,
        )
        location.adjust(
            command.cylinder_type_id,
            command.from_status,
            command.to_status,
            command.quantity,
            performed_by=command.performed_by,
            reason=command.reason,
        )
        await self._repository.save(location)
        await self._unit_of_work.commit()
        return location


# ==========================================================================
# Reconciliation (D-16)
# ==========================================================================


@dataclass(frozen=True, slots=True)
class CreateReconciliationRecordCommand(Command):
    tenant_id: uuid.UUID
    location_type: str
    location_ref_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    status: str
    actual_quantity: int
    recorded_by: uuid.UUID


class CreateReconciliationRecordUseCase:
    """Records a physical count against the tracked balance. **Stock does
    not change here** — only `ApproveReconciliationUseCase` books the
    variance, after someone other than the counter has checked it."""

    def __init__(
        self,
        location_repository: InventoryLocationRepository,
        reconciliation_repository: ReconciliationRecordRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._location_repository = location_repository
        self._reconciliation_repository = reconciliation_repository
        self._unit_of_work = unit_of_work
        self._get_or_create = GetOrCreateInventoryLocationUseCase(location_repository)

    async def execute(
        self, command: CreateReconciliationRecordCommand
    ) -> ReconciliationRecordEntry:
        if command.status not in CYLINDER_STATUSES:
            msg = f"Cylinder status '{command.status}' is not valid."
            raise ValidationError(msg, field="status")
        if command.actual_quantity < 0:
            msg = "The counted quantity cannot be negative."
            raise ValidationError(msg, field="actual_quantity")
        location = await self._get_or_create.execute(
            tenant_id=command.tenant_id,
            location_type=command.location_type,
            location_ref_id=command.location_ref_id,
        )
        # The record needs a real location row to reference, even for a
        # location that has never moved stock (the count may be its first
        # activity). Saving with no pending transactions writes nothing else.
        await self._location_repository.save(location)

        record = await self._reconciliation_repository.create(
            record_id=self._reconciliation_repository.next_id(),
            tenant_id=command.tenant_id,
            inventory_location_id=location.id,
            cylinder_type_id=command.cylinder_type_id,
            status=command.status,
            expected_quantity=location.balance_of(command.cylinder_type_id, command.status),
            actual_quantity=command.actual_quantity,
            recorded_by=command.recorded_by,
        )
        await self._unit_of_work.commit()
        return record


@dataclass(frozen=True, slots=True)
class ApproveReconciliationCommand(Command):
    record_id: uuid.UUID
    approved_by: uuid.UUID
    allow_self_approval: bool = False


class ApproveReconciliationUseCase:
    """Books a pending count's variance into stock, exactly once, by someone
    other than the counter. The record row is locked for the transaction, so
    a double-clicked or repeated approve is a 409, never a second booking."""

    def __init__(
        self,
        repository: ReconciliationRecordRepository,
        location_repository: InventoryLocationRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._location_repository = location_repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: ApproveReconciliationCommand) -> ReconciliationRecordEntry:
        record = await _load_for_decision(self._repository, command.record_id)
        ensure_reconciliation_decidable(
            record_id=record.id,
            recorded_by=record.recorded_by,
            decided_by=command.approved_by,
            approved_at=record.approved_at,
            rejected_at=record.rejected_at,
            allow_self_approval=command.allow_self_approval,
        )
        location = await self._location_repository.get_by_id(record.inventory_location_id)
        if location is None:
            msg = "The stock location for this count no longer exists."
            raise NotFoundError(msg, record_id=str(record.id))
        location.apply_count_variance(
            record.cylinder_type_id,
            record.status,
            record.variance,
            performed_by=command.approved_by,
            reason=f"Physical count approved (expected {record.expected_quantity}, "
            f"counted {record.actual_quantity})",
        )
        await self._location_repository.save(location)
        approved = await self._repository.mark_approved(record.id, approved_by=command.approved_by)
        await self._unit_of_work.commit()
        return approved


@dataclass(frozen=True, slots=True)
class RejectReconciliationCommand(Command):
    record_id: uuid.UUID
    rejected_by: uuid.UUID
    reason: str
    allow_self_approval: bool = False


class RejectReconciliationUseCase:
    """Closes a pending count without touching stock — e.g. it was counted
    in the wrong status, or needs recounting."""

    def __init__(
        self, repository: ReconciliationRecordRepository, unit_of_work: UnitOfWork
    ) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: RejectReconciliationCommand) -> ReconciliationRecordEntry:
        reason = " ".join(command.reason.split())
        if len(reason) < 3:
            msg = "Say why the count is rejected."
            raise ValidationError(msg, field="reason")
        record = await _load_for_decision(self._repository, command.record_id)
        ensure_reconciliation_decidable(
            record_id=record.id,
            recorded_by=record.recorded_by,
            decided_by=command.rejected_by,
            approved_at=record.approved_at,
            rejected_at=record.rejected_at,
            allow_self_approval=command.allow_self_approval,
        )
        rejected = await self._repository.mark_rejected(
            record.id, rejected_by=command.rejected_by, reason=reason
        )
        await self._unit_of_work.commit()
        return rejected


async def _load_for_decision(
    repository: ReconciliationRecordRepository, record_id: uuid.UUID
) -> ReconciliationRecordEntry:
    record = await repository.get_for_decision(record_id)
    if record is None:
        msg = "That stock count was not found."
        raise NotFoundError(msg, record_id=str(record_id))
    return record


@dataclass(frozen=True, slots=True)
class ListReconciliationRecordsQuery(Query):
    tenant_id: uuid.UUID
    location_type: str
    location_ref_id: uuid.UUID
    state: str | None = None
    limit: int = 50


class ListReconciliationRecordsUseCase:
    """Counts at one location — the pending ones are the approver's queue."""

    def __init__(
        self,
        location_repository: InventoryLocationRepository,
        reconciliation_repository: ReconciliationRecordRepository,
    ) -> None:
        self._location_repository = location_repository
        self._reconciliation_repository = reconciliation_repository

    async def execute(
        self, query: ListReconciliationRecordsQuery
    ) -> Sequence[ReconciliationRecordEntry]:
        location = await self._location_repository.get_by_location_ref(
            query.location_type, query.location_ref_id
        )
        if location is None:
            return []
        return await self._reconciliation_repository.list_for_location(
            location.id, state=query.state, limit=query.limit
        )


# ==========================================================================
# Reads
# ==========================================================================


@dataclass(frozen=True, slots=True)
class GetInventoryBalanceQuery(Query):
    tenant_id: uuid.UUID
    location_type: str
    location_ref_id: uuid.UUID


class GetInventoryBalanceUseCase:
    def __init__(self, repository: InventoryLocationRepository) -> None:
        self._repository = repository
        self._get_or_create = GetOrCreateInventoryLocationUseCase(repository)

    async def execute(self, query: GetInventoryBalanceQuery) -> InventoryLocation:
        return await self._get_or_create.execute(
            tenant_id=query.tenant_id,
            location_type=query.location_type,
            location_ref_id=query.location_ref_id,
        )


@dataclass(frozen=True, slots=True)
class ListInventoryTransactionsQuery(Query):
    tenant_id: uuid.UUID
    location_type: str
    location_ref_id: uuid.UUID
    cursor: str | None = None
    limit: int = 50


class ListInventoryTransactionsUseCase:
    def __init__(self, repository: InventoryLocationRepository) -> None:
        self._repository = repository
        self._get_or_create = GetOrCreateInventoryLocationUseCase(repository)

    async def execute(self, query: ListInventoryTransactionsQuery) -> InventoryTransactionPage:
        location = await self._get_or_create.execute(
            tenant_id=query.tenant_id,
            location_type=query.location_type,
            location_ref_id=query.location_ref_id,
        )
        return await self._repository.list_transactions(
            location.id, cursor=query.cursor, limit=query.limit
        )


@dataclass(frozen=True, slots=True)
class GetInventoryOverviewQuery(Query):
    """Zero-argument — built for the AI Command Center's inventory tool
    (ADR-045). Tenant-wide, quantity-by-status only: not broken out by
    cylinder type or by warehouse/vehicle, matching
    `InventoryLocationRepository.get_balance_summary()`'s own scope."""


@dataclass(frozen=True, slots=True)
class InventoryOverview:
    #: e.g. `{"filled": 1200, "empty": 340}` — status vocabulary is
    #: `InventoryLocation`'s own (`filled`/`empty`/etc.), not redefined here.
    quantity_by_status: dict[str, int]


class GetInventoryOverviewUseCase:
    """A thin wrapper around `get_balance_summary()` — that method already
    exists and is already tenant-wide; its only prior caller was
    `GetDashboardSummaryUseCase`, which composes it with unrelated data.
    This is the same read, given its own use case so a tool can call it
    without also pulling every other dashboard field."""

    def __init__(self, repository: InventoryLocationRepository) -> None:
        self._repository = repository

    async def execute(self, query: GetInventoryOverviewQuery) -> InventoryOverview:
        _ = query
        summary = await self._repository.get_balance_summary()
        return InventoryOverview(quantity_by_status=summary)


# ==========================================================================
# Stock register (opening / receipts / issues / closing per day)
# ==========================================================================

#: The register never spans more than this many days in one request.
STOCK_REGISTER_MAX_DAYS = 92


@dataclass(frozen=True, slots=True)
class GetStockRegisterQuery(Query):
    tenant_id: uuid.UUID
    location_type: str
    location_ref_id: uuid.UUID
    date_from: date
    date_to: date
    #: The agency's calendar today — the register's balances are walked
    #: back from today's live balance.
    today: date


@dataclass(frozen=True, slots=True)
class StockRegisterLine:
    business_date: date
    cylinder_type_id: uuid.UUID
    status: str
    opening: int
    receipts: int
    issues: int
    closing: int


class GetStockRegisterUseCase:
    """The daily stock register a distributor keeps per godown: for each day,
    cylinder type and status, the opening balance, what came in, what went
    out and the closing balance.

    Built from the append-only ledger, walked back from today's balance —
    so the register always agrees with the live balance, with no snapshot
    table to drift. A `(type, status)` with no stock and no movement in the
    whole range is left out.
    """

    def __init__(self, repository: InventoryLocationRepository) -> None:
        self._repository = repository

    async def execute(self, query: GetStockRegisterQuery) -> list[StockRegisterLine]:
        if query.date_from > query.date_to:
            msg = "The start date must be on or before the end date."
            raise ValidationError(msg, field="date_from")
        if query.date_to > query.today:
            msg = "The register can't run past today."
            raise ValidationError(msg, field="date_to")
        if (query.date_to - query.date_from).days + 1 > STOCK_REGISTER_MAX_DAYS:
            msg = f"Pick a range of at most {STOCK_REGISTER_MAX_DAYS} days."
            raise ValidationError(msg, field="date_to")

        location = await self._repository.get_by_location_ref(
            query.location_type, query.location_ref_id
        )
        if location is None:
            return []
        movements = await self._repository.list_movements_since(location.id, query.date_from)

        receipts: dict[tuple[date, uuid.UUID, str], int] = {}
        issues: dict[tuple[date, uuid.UUID, str], int] = {}
        net_since: dict[tuple[uuid.UUID, str], int] = {}
        for movement in movements:
            for status, delta in signed_balance_changes(
                movement.transaction_type,
                movement.from_status,
                movement.to_status,
                movement.quantity,
            ):
                key = (movement.cylinder_type_id, status)
                net_since[key] = net_since.get(key, 0) + delta
                bucket = receipts if delta > 0 else issues
                day_key = (movement.business_date, movement.cylinder_type_id, status)
                bucket[day_key] = bucket.get(day_key, 0) + abs(delta)

        keys = set(location.balances) | set(net_since)
        lines: list[StockRegisterLine] = []
        for cylinder_type_id, status in sorted(keys, key=lambda k: (str(k[0]), k[1])):
            current = location.balance_of(cylinder_type_id, status)
            opening = current - net_since.get((cylinder_type_id, status), 0)
            day_lines: list[StockRegisterLine] = []
            day = query.date_from
            while day <= query.date_to:
                received = receipts.get((day, cylinder_type_id, status), 0)
                issued = issues.get((day, cylinder_type_id, status), 0)
                closing = opening + received - issued
                day_lines.append(
                    StockRegisterLine(
                        business_date=day,
                        cylinder_type_id=cylinder_type_id,
                        status=status,
                        opening=opening,
                        receipts=received,
                        issues=issued,
                        closing=closing,
                    )
                )
                opening = closing
                day += timedelta(days=1)
            if any(line.opening or line.receipts or line.issues for line in day_lines):
                lines.extend(day_lines)
        lines.sort(key=lambda line: (line.business_date, str(line.cylinder_type_id), line.status))
        return lines
