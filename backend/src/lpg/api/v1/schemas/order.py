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
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints

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


class OrderCustomerResponse(BaseModel):
    """Who the order is for (DO-12)."""

    id: uuid.UUID
    full_name: str
    phone_number: str
    consumer_number: str | None
    customer_type: str


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
    #: Filled on the order list and order detail reads; `null` elsewhere.
    customer: OrderCustomerResponse | None = None
    #: A post-dispatch cancellation request is waiting for a Manager (CA-07).
    #: Filled on the order list and order detail reads; `false` elsewhere.
    cancellation_pending: bool = False


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
    #: One of the customer's saved addresses; the order snapshots it.
    address_id: uuid.UUID
    #: Deprecated and ignored: the delivery address is always taken from the
    #: customer's saved address `address_id` (free-text addresses are not
    #: accepted). Still accepted so older app builds keep working.
    delivery_address: DeliveryAddressPayload | None = Field(default=None, deprecated=True)
    #: Optional: the server decides from who is booking (a customer login is always
    #: `mobile_app`; staff default to `staff`). Staff may record the channel the customer
    #: used (`phone`, `walk_in`, `whatsapp`) or `api`, but never `mobile_app`.
    booking_source: BookingSource | None = None
    requested_date: datetime
    lines: list[CreateOrderLineRequest] = Field(min_length=1)
    payment_method_preference: PaymentMethod | None = None


class OrderableCylinderTypeResponse(BaseModel):
    """A cylinder type the customer can book right now at the branch:
    active, priced for the customer's type, and in stock."""

    cylinder_type_id: uuid.UUID
    name: str
    weight_kg: Decimal
    #: The price in effect today for this customer's type at the branch. The
    #: order's price is fixed when the agency confirms it.
    unit_price: Decimal
    #: Filled cylinders the branch can still promise to new bookings.
    available_quantity: int


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
    """GPS, payment method and amount are non-optional — a missing one is a
    422 before the request ever reaches `DeliverOrderUseCase`. The signature
    and photo refs are optional (the driver may skip either; the OTP on
    `DeliverOrderRequest` is what gates delivery). `dac_code` is the
    OMC's own separate 6-digit Delivery Authentication Code (Phase 20
    subsystem 4) — optional (coverage is ~90%, not 100%) and format-
    validated only (this platform has no OMC portal API to check a DAC's
    authenticity against); it never gates delivery, unlike `otp_code` on
    `DeliverOrderRequest` below.
    """

    signature_blob_ref: str | None = Field(default=None, min_length=1)
    photo_blob_ref: str | None = Field(default=None, min_length=1)
    gps_lat: Decimal
    gps_lng: Decimal
    payment_method: PaymentMethod
    amount_collected: Decimal = Field(ge=0)
    dac_code: str | None = Field(default=None, pattern=r"^\d{6}$")


class DeliverOrderRequest(BaseModel):
    lines: list[DeliveredLineRequest] = Field(min_length=1)
    otp_code: str = Field(min_length=1)
    proof_of_delivery: ProofOfDeliverySubmission


class ProofOfDeliveryResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    order_id: uuid.UUID
    otp_verified_at: datetime
    signature_blob_ref: str | None = None
    photo_blob_ref: str | None = None
    gps_lat: Decimal
    gps_lng: Decimal
    payment_method: PaymentMethod
    amount_collected: Decimal
    recorded_by: uuid.UUID
    recorded_at: datetime
    dac_code: str | None = None
    #: Short-lived links to view the signature / photo, filled by
    #: `GET /orders/{id}/proof-of-delivery` only.
    signature_url: str | None = None
    photo_url: str | None = None


class DeliverOrderResponse(BaseModel):
    order: OrderResponse
    proof_of_delivery: ProofOfDeliveryResponse


class PodAttachmentResponse(BaseModel):
    blob_ref: str


# ==========================================================================
# Failed delivery
# ==========================================================================


class AmendOrderRequest(BaseModel):
    """Edit a booking before it is put on a trip (DO-13). Omitted fields
    keep their current value; `lines` replaces every line."""

    lines: list[CreateOrderLineRequest] | None = Field(default=None, min_length=1)
    requested_date: datetime | None = None
    #: One of the customer's saved addresses.
    address_id: uuid.UUID | None = None
    payment_method_preference: PaymentMethod | None = None


class RescheduleOrderRequest(BaseModel):
    #: Deliver on this date instead of retrying on the same trip: the order
    #: leaves the trip and goes back to Confirmed, waiting for a new one.
    requested_date: datetime | None = None


class RecordFailedDeliveryRequest(BaseModel):
    reason_code: FailedDeliveryReasonCode
    resolution_action: FailedDeliveryResolutionAction | None = None


# ==========================================================================
# Cancellation
# ==========================================================================


#: A reason someone has to read later: surrounding blanks are dropped, and an
#: empty or blank reason is refused (CA-11).
ReasonText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
    Field(description="Why — required, cannot be blank."),
]


class CancelOrderRequest(BaseModel):
    reason: ReasonText


class CancelOrderResponse(BaseModel):
    order: OrderResponse
    pending_approval: bool


class PendingCancellationResponse(BaseModel):
    """A post-dispatch cancellation request (D-19): waiting for a Manager,
    or — when asked for with `include_decided` — approved or rejected."""

    id: uuid.UUID
    order_id: uuid.UUID
    reason: str
    requested_by: uuid.UUID
    requested_at: datetime
    status: Literal["pending", "approved", "rejected"] = "pending"
    #: What approving a waiting request would charge, per the tenant's
    #: cancellation fee setting. `null` once decided.
    estimated_charge: Decimal | None = None
    #: The charge recorded when the request was approved (billed to the
    #: customer).
    cancellation_charge: Decimal | None = None
    decided_at: datetime | None = None
    rejection_reason: str | None = None


class RejectCancellationRequest(BaseModel):
    reason: ReasonText


class BulkCancelOrdersRequest(BaseModel):
    order_ids: list[uuid.UUID] = Field(min_length=1)
    reason: ReasonText


class BulkCancelOrderResultItem(BaseModel):
    order_id: uuid.UUID
    succeeded: bool
    error_code: str | None = None


class BulkCancelOrdersResponse(BaseModel):
    job_id: str | None
    results: list[BulkCancelOrderResultItem] | None
