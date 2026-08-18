"""FastAPI router for the inventory bounded context.

Exposes warehouse/vehicle cylinder-inventory management under
`/inventory-locations`, `/warehouses`, `/vehicles`, `/inventory` and
`/reconciliation-records`, gated by the permissions in
`docs/data/17-api-security.md` §6:

  inventory:read          — balance / transaction history
  inventory:load           — GRN, load-transfers, deliveries, collections,
                              status-changes, recording a reconciliation count
  inventory:adjust         — manual adjustments
  reconciliation:approve   — approving a reconciliation record (live-checked,
                              `docs/data/17-api-security.md` §7)

Domain and application errors (`DomainError`, `ApplicationError` and their
subclasses, including `NotFoundError`) are never caught here — they
propagate to the global handlers registered in
`lpg.api.middleware.problem_details`, which already map them to the correct
status code, `error_code` and RFC 7807 body. Catching and re-wrapping them
into a generic `HTTPException` here would only lose that mapping (the exact
regression already present in `delivery.py` — see that router's own
now-corrected sibling for what NOT to do here).

Endpoints are addressed by `(location_type, location_ref_id)` — a warehouse
or vehicle id — rather than an opaque `inventory_location_id`, because
`InventoryLocation` rows are created lazily on first use
(`application/inventory/use_cases.py`'s module docstring): a never-touched
warehouse/vehicle has no row and therefore no id a client could supply.
"""

from __future__ import annotations

import uuid
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException

from lpg.api.v1.dependencies.identity import (
    get_current_principal,
    require_live_permission,
    require_permission,
)
from lpg.api.v1.dependencies.inventory import (
    get_goods_receipt_note_repository,
    get_inventory_location_repository,
    get_reconciliation_record_repository,
)
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.api.v1.schemas.inventory import (
    AdjustInventoryRequest,
    ChangeCylinderStatusRequest,
    GoodsReceiptRequest,
    GoodsReceiptResponse,
    InventoryBalanceLine,
    InventoryBalanceResponse,
    InventoryTransactionPageResponse,
    InventoryTransactionResponse,
    LoadTransferRequest,
    LoadTransferResponse,
    LocationType,
    ReconciliationRecordCreateRequest,
    ReconciliationRecordResponse,
    RecordCollectionRequest,
    RecordDeliveryRequest,
)
from lpg.application.common.ports import UnitOfWork
from lpg.application.identity.ports import AuthenticatedPrincipal
from lpg.application.inventory.ports import (
    GoodsReceiptNoteEntry,
    GoodsReceiptNoteRepository,
    InventoryLocationRepository,
    InventoryTransactionEntry,
    ReconciliationRecordEntry,
    ReconciliationRecordRepository,
)
from lpg.application.inventory.use_cases import (
    AdjustInventoryCommand,
    AdjustInventoryUseCase,
    ApproveReconciliationCommand,
    ApproveReconciliationUseCase,
    ChangeCylinderStatusCommand,
    ChangeCylinderStatusUseCase,
    CreateReconciliationRecordCommand,
    CreateReconciliationRecordUseCase,
    GetInventoryBalanceQuery,
    GetInventoryBalanceUseCase,
    ListInventoryTransactionsQuery,
    ListInventoryTransactionsUseCase,
    LoadTransferCommand,
    LoadTransferLine,
    LoadTransferUseCase,
    RecordCollectionCommand,
    RecordCollectionUseCase,
    RecordDeliveryCommand,
    RecordDeliveryUseCase,
    RecordGoodsReceiptCommand,
    RecordGoodsReceiptUseCase,
)
from lpg.domain.inventory.inventory_location import InventoryLocation

router = APIRouter(tags=["Inventory"])


def _require_actor(principal: AuthenticatedPrincipal) -> uuid.UUID:
    if principal.user_id is None:
        raise HTTPException(status_code=401, detail="User ID is required.")
    return principal.user_id


def _location_to_balance_response(
    location: InventoryLocation,
) -> InventoryBalanceResponse:
    return InventoryBalanceResponse(
        location_type=cast("LocationType", location.location_type),
        location_ref_id=location.location_ref_id,
        tenant_id=location.tenant_id,
        balances=[
            InventoryBalanceLine(
                cylinder_type_id=cylinder_type_id, status=status, quantity=quantity
            )
            for (cylinder_type_id, status), quantity in location.balances.items()
        ],
    )


def _transaction_to_response(
    entry: InventoryTransactionEntry,
) -> InventoryTransactionResponse:
    return InventoryTransactionResponse(
        id=entry.id,
        tenant_id=entry.tenant_id,
        inventory_location_id=entry.inventory_location_id,
        cylinder_type_id=entry.cylinder_type_id,
        transaction_type=entry.transaction_type,
        from_status=entry.from_status,
        to_status=entry.to_status,
        quantity=entry.quantity,
        reference_order_id=entry.reference_order_id,
        reason=entry.reason,
        performed_by=entry.performed_by,
        performed_at=entry.performed_at,
    )


def _grn_to_response(entry: GoodsReceiptNoteEntry) -> GoodsReceiptResponse:
    return GoodsReceiptResponse(
        id=entry.id,
        tenant_id=entry.tenant_id,
        warehouse_id=entry.warehouse_id,
        cylinder_type_id=entry.cylinder_type_id,
        quantity_received=entry.quantity_received,
        source_omc=entry.source_omc,
        received_by=entry.received_by,
        received_at=entry.received_at,
    )


def _reconciliation_to_response(
    entry: ReconciliationRecordEntry,
) -> ReconciliationRecordResponse:
    return ReconciliationRecordResponse(
        id=entry.id,
        tenant_id=entry.tenant_id,
        inventory_location_id=entry.inventory_location_id,
        cylinder_type_id=entry.cylinder_type_id,
        status=entry.status,
        expected_quantity=entry.expected_quantity,
        actual_quantity=entry.actual_quantity,
        variance=entry.variance,
        recorded_by=entry.recorded_by,
        approved_by=entry.approved_by,
        approved_at=entry.approved_at,
    )


# ==========================================================================
# Balance / transaction history
# ==========================================================================


@router.get(
    "/inventory-locations/{location_type}/{location_ref_id}/balance",
    response_model=InventoryBalanceResponse,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def get_inventory_balance(
    location_type: LocationType,
    location_ref_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[
        InventoryLocationRepository, Depends(get_inventory_location_repository)
    ],
) -> InventoryBalanceResponse:
    """Current balance for a warehouse or vehicle. All-zero, not 404, if never touched."""
    use_case = GetInventoryBalanceUseCase(repository)
    location = await use_case.execute(
        GetInventoryBalanceQuery(
            tenant_id=principal.tenant_id,
            location_type=location_type,
            location_ref_id=location_ref_id,
        )
    )
    return _location_to_balance_response(location)


@router.get(
    "/inventory-locations/{location_type}/{location_ref_id}/transactions",
    response_model=InventoryTransactionPageResponse,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def list_inventory_transactions(
    location_type: LocationType,
    location_ref_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[
        InventoryLocationRepository, Depends(get_inventory_location_repository)
    ],
    cursor: str | None = None,
    limit: int = 50,
) -> InventoryTransactionPageResponse:
    """Most-recent-first, cursor-paginated transaction history."""
    use_case = ListInventoryTransactionsUseCase(repository)
    page = await use_case.execute(
        ListInventoryTransactionsQuery(
            tenant_id=principal.tenant_id,
            location_type=location_type,
            location_ref_id=location_ref_id,
            cursor=cursor,
            limit=limit,
        )
    )
    return InventoryTransactionPageResponse(
        items=[_transaction_to_response(item) for item in page.items],
        next_cursor=page.next_cursor,
    )


# ==========================================================================
# Goods Receipt (D-15)
# ==========================================================================


@router.post(
    "/warehouses/{warehouse_id}/goods-receipt-notes",
    response_model=GoodsReceiptResponse,
    status_code=201,
    dependencies=[Depends(require_permission("inventory:load"))],
)
async def record_goods_receipt(
    warehouse_id: uuid.UUID,
    request: GoodsReceiptRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    location_repository: Annotated[
        InventoryLocationRepository, Depends(get_inventory_location_repository)
    ],
    grn_repository: Annotated[
        GoodsReceiptNoteRepository, Depends(get_goods_receipt_note_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> GoodsReceiptResponse:
    """Record a Goods Receipt Note — credits the warehouse's Filled balance."""
    actor_id = _require_actor(principal)
    use_case = RecordGoodsReceiptUseCase(
        location_repository, grn_repository, unit_of_work
    )
    grn = await use_case.execute(
        RecordGoodsReceiptCommand(
            tenant_id=principal.tenant_id,
            warehouse_id=warehouse_id,
            cylinder_type_id=request.cylinder_type_id,
            quantity_received=request.quantity_received,
            received_by=actor_id,
            source_omc=request.source_omc,
        )
    )
    return _grn_to_response(grn)


# ==========================================================================
# Load transfer (warehouse -> vehicle)
# ==========================================================================


@router.post(
    "/inventory/load-transfers",
    response_model=LoadTransferResponse,
    status_code=201,
    dependencies=[Depends(require_permission("inventory:load"))],
)
async def create_load_transfer(
    request: LoadTransferRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[
        InventoryLocationRepository, Depends(get_inventory_location_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> LoadTransferResponse:
    """Move stock from a warehouse onto a vehicle — one transaction, or none."""
    actor_id = _require_actor(principal)
    use_case = LoadTransferUseCase(repository, unit_of_work)
    warehouse_location, vehicle_location = await use_case.execute(
        LoadTransferCommand(
            tenant_id=principal.tenant_id,
            warehouse_id=request.warehouse_id,
            vehicle_id=request.vehicle_id,
            lines=[
                LoadTransferLine(
                    cylinder_type_id=line.cylinder_type_id,
                    status=line.status,
                    quantity=line.quantity,
                )
                for line in request.lines
            ],
            performed_by=actor_id,
        )
    )
    return LoadTransferResponse(
        warehouse_balance=_location_to_balance_response(warehouse_location),
        vehicle_balance=_location_to_balance_response(vehicle_location),
    )


# ==========================================================================
# Delivery / collection (vehicle-only)
# ==========================================================================


@router.post(
    "/vehicles/{vehicle_id}/deliveries",
    response_model=InventoryBalanceResponse,
    status_code=201,
    dependencies=[Depends(require_permission("inventory:load"))],
)
async def record_delivery(
    vehicle_id: uuid.UUID,
    request: RecordDeliveryRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[
        InventoryLocationRepository, Depends(get_inventory_location_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> InventoryBalanceResponse:
    """Filled cylinders leave the vehicle to a customer."""
    actor_id = _require_actor(principal)
    use_case = RecordDeliveryUseCase(repository, unit_of_work)
    location = await use_case.execute(
        RecordDeliveryCommand(
            tenant_id=principal.tenant_id,
            vehicle_id=vehicle_id,
            cylinder_type_id=request.cylinder_type_id,
            quantity=request.quantity,
            performed_by=actor_id,
        )
    )
    return _location_to_balance_response(location)


@router.post(
    "/vehicles/{vehicle_id}/collections",
    response_model=InventoryBalanceResponse,
    status_code=201,
    dependencies=[Depends(require_permission("inventory:load"))],
)
async def record_collection(
    vehicle_id: uuid.UUID,
    request: RecordCollectionRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[
        InventoryLocationRepository, Depends(get_inventory_location_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> InventoryBalanceResponse:
    """Empty cylinders are collected from a customer onto the vehicle."""
    actor_id = _require_actor(principal)
    use_case = RecordCollectionUseCase(repository, unit_of_work)
    location = await use_case.execute(
        RecordCollectionCommand(
            tenant_id=principal.tenant_id,
            vehicle_id=vehicle_id,
            cylinder_type_id=request.cylinder_type_id,
            quantity=request.quantity,
            performed_by=actor_id,
        )
    )
    return _location_to_balance_response(location)


# ==========================================================================
# Status change / adjustment
# ==========================================================================


@router.post(
    "/inventory-locations/{location_type}/{location_ref_id}/status-changes",
    response_model=InventoryBalanceResponse,
    status_code=201,
    dependencies=[Depends(require_permission("inventory:load"))],
)
async def change_cylinder_status(
    location_type: LocationType,
    location_ref_id: uuid.UUID,
    request: ChangeCylinderStatusRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[
        InventoryLocationRepository, Depends(get_inventory_location_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> InventoryBalanceResponse:
    """Move stock between statuses at one location (e.g. filled -> leakage).

    409 INVALID_STATUS_TRANSITION if the from/to pair is not permitted.
    """
    actor_id = _require_actor(principal)
    use_case = ChangeCylinderStatusUseCase(repository, unit_of_work)
    location = await use_case.execute(
        ChangeCylinderStatusCommand(
            tenant_id=principal.tenant_id,
            location_type=location_type,
            location_ref_id=location_ref_id,
            cylinder_type_id=request.cylinder_type_id,
            from_status=request.from_status,
            to_status=request.to_status,
            quantity=request.quantity,
            performed_by=actor_id,
        )
    )
    return _location_to_balance_response(location)


@router.post(
    "/inventory-locations/{location_type}/{location_ref_id}/adjustments",
    response_model=InventoryBalanceResponse,
    status_code=201,
    dependencies=[Depends(require_permission("inventory:adjust"))],
)
async def adjust_inventory(
    location_type: LocationType,
    location_ref_id: uuid.UUID,
    request: AdjustInventoryRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[
        InventoryLocationRepository, Depends(get_inventory_location_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> InventoryBalanceResponse:
    """Manual correction. 409 INSUFFICIENT_STOCK / INVALID_STATUS_TRANSITION as applicable."""
    actor_id = _require_actor(principal)
    use_case = AdjustInventoryUseCase(repository, unit_of_work)
    location = await use_case.execute(
        AdjustInventoryCommand(
            tenant_id=principal.tenant_id,
            location_type=location_type,
            location_ref_id=location_ref_id,
            cylinder_type_id=request.cylinder_type_id,
            from_status=request.from_status,
            to_status=request.to_status,
            quantity=request.quantity,
            performed_by=actor_id,
            reason=request.reason,
        )
    )
    return _location_to_balance_response(location)


# ==========================================================================
# Reconciliation (D-16)
# ==========================================================================


@router.post(
    "/inventory-locations/{location_type}/{location_ref_id}/reconciliation-records",
    response_model=ReconciliationRecordResponse,
    status_code=201,
    dependencies=[Depends(require_permission("inventory:load"))],
)
async def create_reconciliation_record(
    location_type: LocationType,
    location_ref_id: uuid.UUID,
    request: ReconciliationRecordCreateRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    location_repository: Annotated[
        InventoryLocationRepository, Depends(get_inventory_location_repository)
    ],
    reconciliation_repository: Annotated[
        ReconciliationRecordRepository, Depends(get_reconciliation_record_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> ReconciliationRecordResponse:
    """Record a physical count against the tracked balance.

    Recording is routine; approval is the gated step.
    """
    actor_id = _require_actor(principal)
    use_case = CreateReconciliationRecordUseCase(
        location_repository, reconciliation_repository, unit_of_work
    )
    record = await use_case.execute(
        CreateReconciliationRecordCommand(
            tenant_id=principal.tenant_id,
            location_type=location_type,
            location_ref_id=location_ref_id,
            cylinder_type_id=request.cylinder_type_id,
            status=request.status,
            actual_quantity=request.actual_quantity,
            recorded_by=actor_id,
        )
    )
    return _reconciliation_to_response(record)


@router.post(
    "/reconciliation-records/{record_id}/approve",
    response_model=ReconciliationRecordResponse,
    dependencies=[Depends(require_live_permission("reconciliation:approve"))],
)
async def approve_reconciliation_record(
    record_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[
        ReconciliationRecordRepository, Depends(get_reconciliation_record_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> ReconciliationRecordResponse:
    """Approve a reconciliation record. Live-checked (`docs/data/17-api-security.md` §7)."""
    actor_id = _require_actor(principal)
    use_case = ApproveReconciliationUseCase(repository, unit_of_work)
    record = await use_case.execute(
        ApproveReconciliationCommand(record_id=record_id, approved_by=actor_id)
    )
    return _reconciliation_to_response(record)
