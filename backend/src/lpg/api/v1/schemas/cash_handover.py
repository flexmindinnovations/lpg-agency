"""Pydantic request/response models for `api/v1/routers/cash_handover.py`.

Like all schemas, `uuid`/`datetime` are real imports.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DeclareCashHandoverRequest(BaseModel):
    driver_id: uuid.UUID
    route_id: uuid.UUID
    actual_amount: Decimal = Field(ge=0)
    #: Count per note or coin value, e.g. `{"500": 4, "100": 3}`. When sent it
    #: must add up to `actual_amount`, and a difference from the expected
    #: cash needs `variance_reason`. Omit both for the earlier amount-only
    #: declaration.
    denominations: dict[int, int] | None = None
    variance_reason: str | None = Field(default=None, max_length=500)


class CashHandoverResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    handover_number: str | None = None
    driver_id: uuid.UUID
    route_id: uuid.UUID
    expected_amount: Decimal
    actual_amount: Decimal
    shortfall: Decimal
    excess: Decimal = Decimal("0")
    declared_by: uuid.UUID
    declared_at: datetime
    denominations: dict[int, int] | None = None
    variance_reason: str | None = None
    upi_expected: Decimal | None = None


class RouteCashHandoverResponse(BaseModel):
    """`GET /cash-handovers/for-route/{route_id}` — the Driver App reads this
    before declaring (to show `expected_amount`) and after (to show the
    receipt). `handover` is null until the driver has declared.
    """

    model_config = ConfigDict(from_attributes=True)

    route_id: uuid.UUID
    driver_id: uuid.UUID
    route_status: str
    route_date: datetime
    expected_amount: Decimal
    cash_stop_count: int
    #: UPI collected at the doorstep on this route, shown beside the cash.
    upi_amount: Decimal = Decimal("0")
    handover: CashHandoverResponse | None = None


class CashHandoverReviewResponse(BaseModel):
    id: uuid.UUID
    outcome: str
    note: str | None
    reviewed_by: uuid.UUID
    reviewed_by_name: str | None = None
    reviewed_at: datetime


class CashHandoverRegisterEntryResponse(BaseModel):
    """One row of the accountant's cash-handover register (DA-33)."""

    id: uuid.UUID
    handover_number: str | None
    driver_id: uuid.UUID
    driver_name: str
    route_id: uuid.UUID
    route_date: datetime
    vehicle_registration: str | None
    cash_stop_count: int
    expected_amount: Decimal
    actual_amount: Decimal
    shortfall: Decimal
    #: Cash handed over beyond what the deliveries account for.
    excess: Decimal
    declared_at: datetime
    denominations: dict[int, int] | None = None
    variance_reason: str | None = None
    upi_expected: Decimal | None = None
    #: `pending` until the office reviews it, then `accepted` or `disputed`.
    review_status: str
    review: CashHandoverReviewResponse | None = None


class ReviewCashHandoverRequest(BaseModel):
    outcome: Literal["accepted", "disputed"]
    note: str | None = Field(default=None, max_length=1000)


class DriverCashInHandResponse(BaseModel):
    driver_id: uuid.UUID
    driver_name: str
    route_count: int
    stop_count: int
    cash_amount: Decimal
    upi_amount: Decimal
    oldest_route_date: datetime


class CashInHandResponse(BaseModel):
    total_cash: Decimal
    drivers: list[DriverCashInHandResponse]


class CashBookCollectionResponse(BaseModel):
    method: str
    payment_count: int
    amount: Decimal


class CashBookResponse(BaseModel):
    """One IST day: money in by mode, and the fate of the cash handed over."""

    date: date
    collections: list[CashBookCollectionResponse]
    total_collected: Decimal
    handover_count: int
    expected_total: Decimal
    handed_over_total: Decimal
    shortfall_total: Decimal
    excess_total: Decimal
    accepted_total: Decimal
    disputed_total: Decimal
    pending_total: Decimal
    pending_count: int
    #: Cash collected on routes still without a handover (not day-bound).
    cash_in_hand_total: Decimal
