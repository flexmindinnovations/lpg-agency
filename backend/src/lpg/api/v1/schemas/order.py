"""Pydantic request/response models for `api/v1/routers/order.py`.

`uuid`/`datetime`/`Decimal` are real imports, not `TYPE_CHECKING`-guarded —
see `schemas/inventory.py`'s identical note on why Pydantic needs them at
class-definition time.

`DeliverOrderRequest.proof_of_delivery`'s fields are all non-optional — the
mechanism that turns a missing/incomplete Proof-of-Delivery submission into
a 422 before the request ever reaches the use case (present-but-invalid
values, e.g. blank refs or out-of-range GPS, are still a 400
`IncompletePodError` raised by `DeliverOrderUseCase`).

`DeliverOrderResponse` deliberately has no `invoice_id`/`ledger_transaction_id`
fields — Accounting/Cylinder Ledger don't exist yet (Phase 12/13); the
fields are absent, not null-faked. See the plan's Context section.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

OrderStatus = Literal[
    "draft",
    "booked",
    "confirmed",
    "assigned",
    "ready_for_dispatch",
    "out_for_delivery",
    "delivered",
    "failed_delivery",
    "cancelled",
    "closed",
]
BookingSource = Literal["mobile_app", "staff", "phone", "walk_in", "whatsapp", "api"]
PaymentMethod = Literal["cash", "upi", "card", "online_gateway", "credit"]
FailedDeliveryReasonCode = Literal[
    "customer_unavailable", "wrong_address", "payment_refused", "vehicle_issue", "safety_issue"
]
FailedDeliveryResolutionAction = Literal["reschedule", "cancel", "return_stock"]

# ==========================================================================
# Shared value objects
# ==========================================================================


class DeliveryAddressPayload(BaseModel):
    address_line: str = Field(min_length=1)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class OrderLineResponse(BaseModel):
    id: uuid.UUID
    cylinder_type_id: uuid.UUID
    quantity_ordered: int
    quantity_delivered: int
    quantity_pending: int
    quantity_collected_empty: int
    is_backordered: bool
    unit_price: Decimal | None


class DriverLocationSnapshot(BaseModel):
    latitude: float
    longitude: float
    heading: float | None = None
    speed_kph: float | None = None
    accuracy_m: float | None = None
    recorded_at: datetime


class TrackingDriverInfo(BaseModel):
    """The assigned driver + vehicle, shown on the tracking screen. Present
    once the order is on a route."""

    name: str
    phone_number: str | None = None
    vehicle_number: str | None = None
    vehicle_model: str | None = None


class OrderTrackingResponse(BaseModel):
    """Everything the customer app's order-tracking map needs beyond what it
    already has from the order itself: the resolved route status, the driver's
    last-known position (``None`` until the driver starts sharing), and the
    assigned driver + vehicle.
    """

    order_id: uuid.UUID
    status: OrderStatus
    destination_latitude: float | None
    destination_longitude: float | None
    destination_label: str
    route_status: str | None
    driver_location: DriverLocationSnapshot | None
    driver: TrackingDriverInfo | None = None


class OrderResponse(BaseModel):
    id: uuid.UUID
    order_number: str | None = None
    tenant_id: uuid.UUID
    branch_id: uuid.UUID
    customer_id: uuid.UUID
    address_id: uuid.UUID
    delivery_address: DeliveryAddressPayload
    status: OrderStatus
    booking_source: BookingSource
    payment_method_preference: PaymentMethod | None
    requested_date: datetime
    metadata: dict[str, Any]
    route_stop_id: uuid.UUID | None
    total_amount: Decimal | None
    lines: list[OrderLineResponse]


class OrderPageResponse(BaseModel):
    items: list[OrderResponse]
    total: int


class OrderStatusHistoryEntryResponse(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    from_status: OrderStatus | None
    to_status: OrderStatus
    changed_by: uuid.UUID
    changed_at: datetime
    reason: str | None


# ==========================================================================
# Create / Confirm
# ==========================================================================


class CreateOrderLineRequest(BaseModel):
    cylinder_type_id: uuid.UUID
    quantity: int = Field(ge=1)


class CreateOrderRequest(BaseModel):
    branch_id: uuid.UUID
    customer_id: uuid.UUID
    address_id: uuid.UUID
    delivery_address: DeliveryAddressPayload
    booking_source: BookingSource
    requested_date: datetime
    lines: list[CreateOrderLineRequest] = Field(min_length=1)
    payment_method_preference: PaymentMethod | None = None


# ==========================================================================
# Assign
# ==========================================================================


class AssignOrderRequest(BaseModel):
    driver_id: uuid.UUID
    vehicle_id: uuid.UUID


# ==========================================================================
# Deliver (atomic: Order + vehicle InventoryLocation + ProofOfDelivery)
# ==========================================================================


class DeliveredLineRequest(BaseModel):
    cylinder_type_id: uuid.UUID
    quantity_delivered: int = Field(ge=0)
    quantity_collected_empty: int = Field(default=0, ge=0)


class ProofOfDeliverySubmission(BaseModel):
    """All five fields are non-optional — a missing one is a 422 before the
    request ever reaches `DeliverOrderUseCase`.
    """

    signature_blob_ref: str = Field(min_length=1)
    photo_blob_ref: str = Field(min_length=1)
    gps_lat: Decimal
    gps_lng: Decimal
    payment_method: PaymentMethod
    amount_collected: Decimal = Field(ge=0)


class DeliverOrderRequest(BaseModel):
    lines: list[DeliveredLineRequest] = Field(min_length=1)
    otp_code: str = Field(min_length=1)
    proof_of_delivery: ProofOfDeliverySubmission


class ProofOfDeliveryResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    order_id: uuid.UUID
    otp_verified_at: datetime
    signature_blob_ref: str
    photo_blob_ref: str
    gps_lat: Decimal
    gps_lng: Decimal
    payment_method: PaymentMethod
    amount_collected: Decimal
    recorded_by: uuid.UUID
    recorded_at: datetime


class DeliverOrderResponse(BaseModel):
    order: OrderResponse
    proof_of_delivery: ProofOfDeliveryResponse


class PodAttachmentResponse(BaseModel):
    blob_ref: str


# ==========================================================================
# Failed delivery
# ==========================================================================


class RecordFailedDeliveryRequest(BaseModel):
    reason_code: FailedDeliveryReasonCode
    resolution_action: FailedDeliveryResolutionAction | None = None


# ==========================================================================
# Cancellation
# ==========================================================================


class CancelOrderRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class CancelOrderResponse(BaseModel):
    order: OrderResponse
    pending_approval: bool


class BulkCancelOrdersRequest(BaseModel):
    order_ids: list[uuid.UUID] = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=1000)


class BulkCancelOrderResultItem(BaseModel):
    order_id: uuid.UUID
    succeeded: bool
    error_code: str | None = None


class BulkCancelOrdersResponse(BaseModel):
    job_id: str | None
    results: list[BulkCancelOrderResultItem] | None
