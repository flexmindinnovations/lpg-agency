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
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command, Query
from lpg.domain.inventory.inventory_location import InventoryLocation

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
            source_omc=command.source_omc,
            received_by=command.received_by,
            grn_number=grn_number,
        )
        await self._unit_of_work.commit()
        return grn


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
        location = await self._get_or_create.execute(
            tenant_id=command.tenant_id,
            location_type=command.location_type,
            location_ref_id=command.location_ref_id,
        )
        # Read before reconcile() overwrites it — reconcile() sets the
        # tracked balance directly to actual_quantity.
        expected_quantity = location.balance_of(command.cylinder_type_id, command.status)
        location.reconcile(
            command.cylinder_type_id,
            command.status,
            command.actual_quantity,
            performed_by=command.recorded_by,
        )
        await self._location_repository.save(location)

        record = await self._reconciliation_repository.create(
            record_id=self._reconciliation_repository.next_id(),
            tenant_id=command.tenant_id,
            inventory_location_id=location.id,
            cylinder_type_id=command.cylinder_type_id,
            status=command.status,
            expected_quantity=expected_quantity,
            actual_quantity=command.actual_quantity,
            recorded_by=command.recorded_by,
        )
        await self._unit_of_work.commit()
        return record


@dataclass(frozen=True, slots=True)
class ApproveReconciliationCommand(Command):
    record_id: uuid.UUID
    approved_by: uuid.UUID


class ApproveReconciliationUseCase:
    def __init__(
        self, repository: ReconciliationRecordRepository, unit_of_work: UnitOfWork
    ) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: ApproveReconciliationCommand) -> ReconciliationRecordEntry:
        record = await self._repository.approve(command.record_id, approved_by=command.approved_by)
        await self._unit_of_work.commit()
        return record


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
