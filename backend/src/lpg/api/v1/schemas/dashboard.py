"""Pydantic response models for `api/v1/routers/dashboard.py`.

`uuid`/`datetime`/`Decimal` are real imports, not `TYPE_CHECKING`-guarded —
see `schemas/inventory.py`'s identical note on why Pydantic needs them at
class-definition time.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class CylinderTypePriceCardResponse(BaseModel):
    cylinder_type_id: uuid.UUID
    name: str
    weight_kg: Decimal
    customer_type: str
    #: `None` when no price list entry has been configured yet.
    price: Decimal | None


class DashboardActivityEntryResponse(BaseModel):
    id: uuid.UUID
    actor_display_name: str | None
    entity_name: str
    entity_id: str | None
    entity_display_name: str | None
    action: str
    performed_at: datetime


class DashboardSummaryResponse(BaseModel):
    customer_count: int
    driver_count: int
    vehicle_count: int
    vehicles_by_status: dict[str, int]
    warehouse_count: int
    cylinder_type_count: int
    inventory_by_status: dict[str, int]
    price_cards: list[CylinderTypePriceCardResponse]
    #: `before_state`/`after_state` aren't surfaced here — the dashboard's
    #: activity feed is a glance-level summary, not the full audit trail
    #: (that detail is `GET /admin/audit-log`'s job).
    recent_activity: list[DashboardActivityEntryResponse]


class OrderPipelineResponse(BaseModel):
    bookings_today: int
    #: Orders now in each open status, `booked` through `failed_delivery`.
    open_by_status: dict[str, int]
    delivered_today: int
    failed_today: int
    pending_cancellations: int


class InvoiceSnapshotResponse(BaseModel):
    outstanding_count: int
    outstanding_amount: Decimal
    overdue_count: int
    overdue_amount: Decimal
    #: Delivered orders or billed cancellations with no invoice yet.
    on_hold_count: int


class CashSnapshotResponse(BaseModel):
    #: Cash drivers collected on routes with no handover declared yet.
    awaiting_handover: Decimal
    handovers_awaiting_review: int


class OperationsSnapshotResponse(BaseModel):
    """The Home page's operations KPIs (DO-28). `invoices`/`cash` are
    `null` for a caller without access to those modules.
    """

    orders: OrderPipelineResponse
    open_complaints: int
    low_stock_count: int
    invoices: InvoiceSnapshotResponse | None
    cash: CashSnapshotResponse | None
    payment_terms_days: int
