"""Pydantic request/response models for `api/v1/routers/inventory.py`.

`uuid`/`datetime` are real imports, not `TYPE_CHECKING`-guarded — see
`schemas/delivery.py`'s identical note on why Pydantic needs them at
class-definition time.

`InventoryTransactionResponse.performed_at` / `GoodsReceiptResponse.received_at`
are genuine domain-carried timestamps sourced from the persisted row —
unlike Driver/Vehicle's `created_at`/`updated_at` (which those aggregates
don't track and which `delivery.py`'s schemas correctly omit), these are
real business data, not fabricated at mapping time.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

LocationType = Literal["warehouse", "vehicle"]
#: Mirrors `domain.inventory.inventory_location.OMC_CODES`.
OmcCode = Literal["iocl", "bpcl", "hpcl", "other"]
CylinderStatus = Literal["filled", "empty", "damaged", "leakage", "quarantine", "repair", "scrap"]
#: Mirrors `OMC_RETURNABLE_STATUSES`.
OmcReturnableStatus = Literal["empty", "damaged", "leakage", "quarantine"]
ReconciliationState = Literal["pending", "approved", "rejected"]

# ==========================================================================
# Balance
# ==========================================================================


class InventoryBalanceLine(BaseModel):
    cylinder_type_id: uuid.UUID
    status: str
    quantity: int


class InventoryBalanceResponse(BaseModel):
    location_type: LocationType
    location_ref_id: uuid.UUID
    tenant_id: uuid.UUID
    balances: list[InventoryBalanceLine]


# ==========================================================================
# Goods Receipt (D-15)
# ==========================================================================


class GoodsReceiptRequest(BaseModel):
    cylinder_type_id: uuid.UUID
    quantity_received: int = Field(ge=1)
    source_omc: OmcCode | None = None
    #: The OMC's delivery challan / tax invoice and the truck's registration.
    challan_number: str | None = Field(default=None, max_length=50)
    invoice_number: str | None = Field(default=None, max_length=50)
    truck_number: str | None = Field(default=None, max_length=20)


class GoodsReceiptResponse(BaseModel):
    id: uuid.UUID
    grn_number: str | None = None
    tenant_id: uuid.UUID
    warehouse_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    quantity_received: int
    source_omc: str | None
    challan_number: str | None = None
    invoice_number: str | None = None
    truck_number: str | None = None
    received_by: uuid.UUID
    received_at: datetime


class OmcReturnRequest(BaseModel):
    """Empties (or segregated defective cylinders) going back to the plant."""

    cylinder_type_id: uuid.UUID
    quantity: int = Field(ge=1)
    destination_omc: OmcCode
    status: OmcReturnableStatus = "empty"
    challan_number: str | None = Field(default=None, max_length=50)
    truck_number: str | None = Field(default=None, max_length=20)


class OmcReturnResponse(BaseModel):
    id: uuid.UUID
    return_number: str
    warehouse_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    status: str
    quantity: int
    destination_omc: str
    challan_number: str | None
    truck_number: str | None
    dispatched_by: uuid.UUID
    dispatched_at: datetime


# ==========================================================================
# Load transfer (warehouse -> vehicle)
# ==========================================================================


class LoadTransferLineRequest(BaseModel):
    cylinder_type_id: uuid.UUID
    status: str
    quantity: int = Field(ge=1)


class LoadTransferRequest(BaseModel):
    warehouse_id: uuid.UUID
    vehicle_id: uuid.UUID
    lines: list[LoadTransferLineRequest] = Field(min_length=1)


class LoadTransferResponse(BaseModel):
    warehouse_balance: InventoryBalanceResponse
    vehicle_balance: InventoryBalanceResponse


# ==========================================================================
# Delivery / collection (vehicle-only)
# ==========================================================================


class RecordDeliveryRequest(BaseModel):
    cylinder_type_id: uuid.UUID
    quantity: int = Field(ge=1)


class RecordCollectionRequest(BaseModel):
    cylinder_type_id: uuid.UUID
    quantity: int = Field(ge=1)


# ==========================================================================
# Status change / adjustment
# ==========================================================================


class ChangeCylinderStatusRequest(BaseModel):
    cylinder_type_id: uuid.UUID
    from_status: CylinderStatus
    to_status: CylinderStatus
    quantity: int = Field(ge=1)


class AdjustInventoryRequest(BaseModel):
    cylinder_type_id: uuid.UUID
    from_status: CylinderStatus
    to_status: CylinderStatus
    quantity: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)


# ==========================================================================
# Reconciliation (D-16)
# ==========================================================================


class ReconciliationRecordCreateRequest(BaseModel):
    cylinder_type_id: uuid.UUID
    status: CylinderStatus
    actual_quantity: int = Field(ge=0)


class ReconciliationRejectRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class ReconciliationRecordResponse(BaseModel):
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
    #: `pending` until someone other than the counter approves or rejects it.
    state: ReconciliationState = "pending"
    recorded_at: datetime | None = None
    rejected_by: uuid.UUID | None = None
    rejected_at: datetime | None = None
    rejection_reason: str | None = None


class ReconciliationRecordListResponse(BaseModel):
    items: list[ReconciliationRecordResponse]


# ==========================================================================
# Status rules and stock register
# ==========================================================================


class StatusTransitionsResponse(BaseModel):
    """The legal target statuses for each status — the same rule the server
    enforces, so a client never offers a move that would be refused."""

    status_change: dict[str, list[str]]
    adjustment: dict[str, list[str]]


class StockRegisterLineResponse(BaseModel):
    date: date
    cylinder_type_id: uuid.UUID
    status: str
    opening: int
    receipts: int
    issues: int
    closing: int


class StockRegisterResponse(BaseModel):
    location_type: LocationType
    location_ref_id: uuid.UUID
    date_from: date
    date_to: date
    lines: list[StockRegisterLineResponse]


# ==========================================================================
# Transaction history
# ==========================================================================


class InventoryTransactionResponse(BaseModel):
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


class InventoryTransactionPageResponse(BaseModel):
    items: list[InventoryTransactionResponse]
    next_cursor: str | None


# ==========================================================================
# Reorder policy (AI Operational Intelligence, Horizon 1 Stage 4)
# ==========================================================================


class SetReorderPolicyRequest(BaseModel):
    """Addressed by `warehouse_id`, not the internal `inventory_location_id`
    — v1 scope is warehouses only; see `application/inventory/reorder.py`'s
    module docstring. The location row is lazily created if this warehouse
    has never had inventory activity yet."""

    warehouse_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    reorder_point: int = Field(ge=0)
    safety_stock: int = Field(ge=0, default=0)


class ReorderPolicyResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    inventory_location_id: uuid.UUID
    #: The warehouse this policy is set on — always a `warehouse_id`,
    #: since v1 scope is warehouses only.
    location_ref_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    reorder_point: int
    safety_stock: int
    last_reorder_notified_at: datetime | None
    updated_by: uuid.UUID | None
    updated_at: datetime


class ReorderPolicyListResponse(BaseModel):
    items: list[ReorderPolicyResponse]


class ReorderSignalResponse(BaseModel):
    """One currently-breached `(location, cylinder_type)` — a heuristic
    threshold comparison, not a guarantee; recorded to `ai.prediction`
    (`model_version="reorder_threshold_v1"`) by the daily cron."""

    policy_id: uuid.UUID
    inventory_location_id: uuid.UUID
    location_ref_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    on_hand: int
    reorder_point: int
    safety_stock: int
    last_reorder_notified_at: datetime | None


class ReorderSignalListResponse(BaseModel):
    items: list[ReorderSignalResponse]
