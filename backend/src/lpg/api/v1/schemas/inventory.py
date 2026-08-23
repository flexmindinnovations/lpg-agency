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
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

LocationType = Literal["warehouse", "vehicle"]

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
    source_omc: str | None = None


class GoodsReceiptResponse(BaseModel):
    id: uuid.UUID
    grn_number: str | None = None
    tenant_id: uuid.UUID
    warehouse_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    quantity_received: int
    source_omc: str | None
    received_by: uuid.UUID
    received_at: datetime


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
    from_status: str
    to_status: str
    quantity: int = Field(ge=1)


class AdjustInventoryRequest(BaseModel):
    cylinder_type_id: uuid.UUID
    from_status: str
    to_status: str
    quantity: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)


# ==========================================================================
# Reconciliation (D-16)
# ==========================================================================


class ReconciliationRecordCreateRequest(BaseModel):
    cylinder_type_id: uuid.UUID
    status: str
    actual_quantity: int = Field(ge=0)


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
