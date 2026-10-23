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
from datetime import UTC, date, datetime
from typing import Annotated, cast
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query

from lpg.api.v1.dependencies.identity import (
    get_current_principal,
    require_live_permission,
    require_permission,
)
from lpg.api.v1.dependencies.inventory import (
    get_goods_receipt_note_repository,
    get_grn_number_sequence,
    get_inventory_location_repository,
    get_omc_return_note_repository,
    get_omc_return_number_sequence,
    get_reconciliation_record_repository,
    get_reorder_policy_repository,
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
    OmcReturnRequest,
    OmcReturnResponse,
    ReconciliationRecordCreateRequest,
    ReconciliationRecordListResponse,
    ReconciliationRecordResponse,
    ReconciliationRejectRequest,
    ReconciliationState,
    RecordCollectionRequest,
    RecordDeliveryRequest,
    ReorderPolicyListResponse,
    ReorderPolicyResponse,
    ReorderSignalListResponse,
    ReorderSignalResponse,
    SetReorderPolicyRequest,
    StatusTransitionsResponse,
    StockRegisterLineResponse,
    StockRegisterResponse,
)
from lpg.application.common.ports import UnitOfWork
from lpg.application.identity.ports import AuthenticatedPrincipal
from lpg.application.inventory.ports import (
    GoodsReceiptNoteEntry,
    GoodsReceiptNoteRepository,
    GrnNumberSequence,
    InventoryLocationRepository,
    InventoryTransactionEntry,
    OmcReturnNoteEntry,
    OmcReturnNoteRepository,
    OmcReturnNumberSequence,
    ReconciliationRecordEntry,
    ReconciliationRecordRepository,
    ReorderPolicy,
    ReorderPolicyRepository,
    ReorderSignal,
)
from lpg.application.inventory.reorder import (
    ListReorderPoliciesQuery,
    ListReorderPoliciesUseCase,
    ListReorderSignalsQuery,
    ListReorderSignalsUseCase,
    SetReorderPolicyCommand,
    SetReorderPolicyUseCase,
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
    GetOrCreateInventoryLocationUseCase,
    GetStockRegisterQuery,
    GetStockRegisterUseCase,
    ListInventoryTransactionsQuery,
    ListInventoryTransactionsUseCase,
    ListReconciliationRecordsQuery,
    ListReconciliationRecordsUseCase,
    LoadTransferCommand,
    LoadTransferLine,
    LoadTransferUseCase,
    RecordCollectionCommand,
    RecordCollectionUseCase,
    RecordDeliveryCommand,
    RecordDeliveryUseCase,
    RecordGoodsReceiptCommand,
    RecordGoodsReceiptUseCase,
    RejectReconciliationCommand,
    RejectReconciliationUseCase,
    ReturnStockToOmcCommand,
    ReturnStockToOmcUseCase,
)
from lpg.domain.inventory.inventory_location import (
    InventoryLocation,
    adjustment_targets,
    status_change_targets,
)

#: The agency's calendar — the stock register's "today".
_BUSINESS_TZ = ZoneInfo("Asia/Kolkata")

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
        grn_number=entry.grn_number,
        tenant_id=entry.tenant_id,
        warehouse_id=entry.warehouse_id,
        cylinder_type_id=entry.cylinder_type_id,
        quantity_received=entry.quantity_received,
        source_omc=entry.source_omc,
        challan_number=entry.challan_number,
        invoice_number=entry.invoice_number,
        truck_number=entry.truck_number,
        received_by=entry.received_by,
        received_at=entry.received_at,
    )


def _omc_return_to_response(entry: OmcReturnNoteEntry) -> OmcReturnResponse:
    return OmcReturnResponse(
        id=entry.id,
        return_number=entry.return_number,
        warehouse_id=entry.warehouse_id,
        cylinder_type_id=entry.cylinder_type_id,
        status=entry.status,
        quantity=entry.quantity,
        destination_omc=entry.destination_omc,
        challan_number=entry.challan_number,
        truck_number=entry.truck_number,
        dispatched_by=entry.dispatched_by,
        dispatched_at=entry.dispatched_at,
    )


def _reorder_policy_to_response(policy: ReorderPolicy) -> ReorderPolicyResponse:
    return ReorderPolicyResponse(
        id=policy.id,
        tenant_id=policy.tenant_id,
        inventory_location_id=policy.inventory_location_id,
        location_ref_id=policy.location_ref_id,
        cylinder_type_id=policy.cylinder_type_id,
        reorder_point=policy.reorder_point,
        safety_stock=policy.safety_stock,
        last_reorder_notified_at=policy.last_reorder_notified_at,
        updated_by=policy.updated_by,
        updated_at=policy.updated_at,
    )


def _reorder_signal_to_response(signal: ReorderSignal) -> ReorderSignalResponse:
    return ReorderSignalResponse(
        policy_id=signal.policy_id,
        inventory_location_id=signal.inventory_location_id,
        location_ref_id=signal.location_ref_id,
        cylinder_type_id=signal.cylinder_type_id,
        on_hand=signal.on_hand,
        reorder_point=signal.reorder_point,
        safety_stock=signal.safety_stock,
        last_reorder_notified_at=signal.last_reorder_notified_at,
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
        state=cast("ReconciliationState", entry.state),
        recorded_at=entry.recorded_at,
        rejected_by=entry.rejected_by,
        rejected_at=entry.rejected_at,
        rejection_reason=entry.rejection_reason,
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
    repository: Annotated[InventoryLocationRepository, Depends(get_inventory_location_repository)],
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
    repository: Annotated[InventoryLocationRepository, Depends(get_inventory_location_repository)],
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


@router.get(
    "/inventory-locations/{location_type}/{location_ref_id}/stock-register",
    response_model=StockRegisterResponse,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def get_stock_register(
    location_type: LocationType,
    location_ref_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[InventoryLocationRepository, Depends(get_inventory_location_repository)],
    date_from: date,
    date_to: date,
) -> StockRegisterResponse:
    """Daily stock register: opening, receipts, issues and closing per
    cylinder type and status, for each IST day in the range (max 92 days)."""
    lines = await GetStockRegisterUseCase(repository).execute(
        GetStockRegisterQuery(
            tenant_id=principal.tenant_id,
            location_type=location_type,
            location_ref_id=location_ref_id,
            date_from=date_from,
            date_to=date_to,
            today=datetime.now(UTC).astimezone(_BUSINESS_TZ).date(),
        )
    )
    return StockRegisterResponse(
        location_type=location_type,
        location_ref_id=location_ref_id,
        date_from=date_from,
        date_to=date_to,
        lines=[
            StockRegisterLineResponse(
                date=line.business_date,
                cylinder_type_id=line.cylinder_type_id,
                status=line.status,
                opening=line.opening,
                receipts=line.receipts,
                issues=line.issues,
                closing=line.closing,
            )
            for line in lines
        ],
    )


@router.get(
    "/inventory/status-transitions",
    response_model=StatusTransitionsResponse,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def get_status_transitions() -> StatusTransitionsResponse:
    """Which status each status may move to, for Change Status and Adjust."""
    return StatusTransitionsResponse(
        status_change={k: sorted(v) for k, v in status_change_targets().items()},
        adjustment={k: sorted(v) for k, v in adjustment_targets().items()},
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
    grn_number_sequence: Annotated[GrnNumberSequence, Depends(get_grn_number_sequence)],
) -> GoodsReceiptResponse:
    """Record a Goods Receipt Note — credits the warehouse's Filled balance."""
    actor_id = _require_actor(principal)
    use_case = RecordGoodsReceiptUseCase(
        location_repository, grn_repository, unit_of_work, grn_number_sequence
    )
    grn = await use_case.execute(
        RecordGoodsReceiptCommand(
            tenant_id=principal.tenant_id,
            warehouse_id=warehouse_id,
            cylinder_type_id=request.cylinder_type_id,
            quantity_received=request.quantity_received,
            received_by=actor_id,
            source_omc=request.source_omc,
            challan_number=request.challan_number,
            invoice_number=request.invoice_number,
            truck_number=request.truck_number,
        )
    )
    return _grn_to_response(grn)


@router.post(
    "/warehouses/{warehouse_id}/omc-returns",
    response_model=OmcReturnResponse,
    status_code=201,
    dependencies=[Depends(require_permission("inventory:load"))],
)
async def return_stock_to_omc(
    warehouse_id: uuid.UUID,
    request: OmcReturnRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    location_repository: Annotated[
        InventoryLocationRepository, Depends(get_inventory_location_repository)
    ],
    note_repository: Annotated[OmcReturnNoteRepository, Depends(get_omc_return_note_repository)],
    number_sequence: Annotated[OmcReturnNumberSequence, Depends(get_omc_return_number_sequence)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> OmcReturnResponse:
    """Dispatch empties (or segregated defective cylinders) back to the OMC's
    bottling plant — debits the warehouse and issues a numbered return note.
    409 INSUFFICIENT_STOCK if the warehouse holds fewer."""
    actor_id = _require_actor(principal)
    use_case = ReturnStockToOmcUseCase(
        location_repository, note_repository, number_sequence, unit_of_work
    )
    note = await use_case.execute(
        ReturnStockToOmcCommand(
            tenant_id=principal.tenant_id,
            warehouse_id=warehouse_id,
            cylinder_type_id=request.cylinder_type_id,
            quantity=request.quantity,
            destination_omc=request.destination_omc,
            status=request.status,
            challan_number=request.challan_number,
            truck_number=request.truck_number,
            dispatched_by=actor_id,
        )
    )
    return _omc_return_to_response(note)


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
    repository: Annotated[InventoryLocationRepository, Depends(get_inventory_location_repository)],
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
    repository: Annotated[InventoryLocationRepository, Depends(get_inventory_location_repository)],
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
    repository: Annotated[InventoryLocationRepository, Depends(get_inventory_location_repository)],
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
    repository: Annotated[InventoryLocationRepository, Depends(get_inventory_location_repository)],
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
    repository: Annotated[InventoryLocationRepository, Depends(get_inventory_location_repository)],
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
    """Record a physical count against the tracked balance. Stock does not
    change until someone else approves the count.
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


@router.get(
    "/inventory-locations/{location_type}/{location_ref_id}/reconciliation-records",
    response_model=ReconciliationRecordListResponse,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def list_reconciliation_records(
    location_type: LocationType,
    location_ref_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    location_repository: Annotated[
        InventoryLocationRepository, Depends(get_inventory_location_repository)
    ],
    reconciliation_repository: Annotated[
        ReconciliationRecordRepository, Depends(get_reconciliation_record_repository)
    ],
    state: ReconciliationState | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ReconciliationRecordListResponse:
    """Stock counts at this location, newest first — `state=pending` is the
    approver's queue."""
    records = await ListReconciliationRecordsUseCase(
        location_repository, reconciliation_repository
    ).execute(
        ListReconciliationRecordsQuery(
            tenant_id=principal.tenant_id,
            location_type=location_type,
            location_ref_id=location_ref_id,
            state=state,
            limit=limit,
        )
    )
    return ReconciliationRecordListResponse(
        items=[_reconciliation_to_response(record) for record in records]
    )


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
    location_repository: Annotated[
        InventoryLocationRepository, Depends(get_inventory_location_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> ReconciliationRecordResponse:
    """Approve a pending count and book its variance into stock, once.
    Live-checked (`docs/data/17-api-security.md` §7). 409
    `RECONCILIATION_ALREADY_DECIDED` on a repeat, 409
    `SELF_APPROVAL_NOT_ALLOWED` for the person who counted."""
    actor_id = _require_actor(principal)
    allow_self = principal.role in ("agency_admin", "super_admin")
    use_case = ApproveReconciliationUseCase(repository, location_repository, unit_of_work)
    record = await use_case.execute(
        ApproveReconciliationCommand(
            record_id=record_id, approved_by=actor_id, allow_self_approval=allow_self
        )
    )
    return _reconciliation_to_response(record)


@router.post(
    "/reconciliation-records/{record_id}/reject",
    response_model=ReconciliationRecordResponse,
    dependencies=[Depends(require_live_permission("reconciliation:approve"))],
)
async def reject_reconciliation_record(
    record_id: uuid.UUID,
    request: ReconciliationRejectRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[
        ReconciliationRecordRepository, Depends(get_reconciliation_record_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> ReconciliationRecordResponse:
    """Close a pending count without changing stock (e.g. recount needed)."""
    actor_id = _require_actor(principal)
    allow_self = principal.role in ("agency_admin", "super_admin")
    record = await RejectReconciliationUseCase(repository, unit_of_work).execute(
        RejectReconciliationCommand(
            record_id=record_id,
            rejected_by=actor_id,
            reason=request.reason,
            allow_self_approval=allow_self,
        )
    )
    return _reconciliation_to_response(record)


# ==========================================================================
# Reorder policy (AI Operational Intelligence, Horizon 1 Stage 4)
# ==========================================================================


@router.put(
    "/inventory/reorder-policy",
    response_model=ReorderPolicyResponse,
    dependencies=[Depends(require_permission("inventory:adjust"))],
)
async def set_reorder_policy(
    request: SetReorderPolicyRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    location_repository: Annotated[
        InventoryLocationRepository, Depends(get_inventory_location_repository)
    ],
    reorder_policy_repository: Annotated[
        ReorderPolicyRepository, Depends(get_reorder_policy_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> ReorderPolicyResponse:
    """Set or edit the reorder threshold for one warehouse x cylinder type.
    Addressed by `warehouse_id` (v1 scope is warehouses only — see
    `application/inventory/reorder.py`'s module docstring), lazily
    persisting the `InventoryLocation` row if this warehouse has never had
    inventory activity yet — the same "no row until first mutation" shape
    `GetOrCreateInventoryLocationUseCase` already documents, made real
    here since `reorder_policy.inventory_location_id` is a genuine FK.
    """
    actor_id = _require_actor(principal)
    location = await GetOrCreateInventoryLocationUseCase(location_repository).execute(
        tenant_id=principal.tenant_id,
        location_type="warehouse",
        location_ref_id=request.warehouse_id,
    )
    await location_repository.save(location)

    use_case = SetReorderPolicyUseCase(reorder_policy_repository, unit_of_work)
    policy = await use_case.execute(
        SetReorderPolicyCommand(
            tenant_id=principal.tenant_id,
            inventory_location_id=location.id,
            cylinder_type_id=request.cylinder_type_id,
            reorder_point=request.reorder_point,
            safety_stock=request.safety_stock,
            updated_by=actor_id,
        )
    )
    return _reorder_policy_to_response(policy)


@router.get(
    "/inventory/reorder-policy",
    response_model=ReorderPolicyListResponse,
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def list_reorder_policies(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    reorder_policy_repository: Annotated[
        ReorderPolicyRepository, Depends(get_reorder_policy_repository)
    ],
) -> ReorderPolicyListResponse:
    use_case = ListReorderPoliciesUseCase(reorder_policy_repository)
    policies = await use_case.execute(ListReorderPoliciesQuery(tenant_id=principal.tenant_id))
    return ReorderPolicyListResponse(items=[_reorder_policy_to_response(p) for p in policies])


@router.get(
    "/inventory/reorder-signals",
    response_model=ReorderSignalListResponse,
    summary="Currently-breached reorder thresholds",
    dependencies=[Depends(require_permission("inventory:read"))],
)
async def list_reorder_signals(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    reorder_policy_repository: Annotated[
        ReorderPolicyRepository, Depends(get_reorder_policy_repository)
    ],
) -> ReorderSignalListResponse:
    """Pure read — a heuristic threshold comparison, not a guarantee; the
    daily `check_reorder_levels` cron is what actually records these to
    `ai.prediction` and notifies staff. This endpoint recomputes the same
    comparison live, with no side effect of its own."""
    use_case = ListReorderSignalsUseCase(reorder_policy_repository)
    signals = await use_case.execute(ListReorderSignalsQuery(tenant_id=principal.tenant_id))
    return ReorderSignalListResponse(items=[_reorder_signal_to_response(s) for s in signals])
