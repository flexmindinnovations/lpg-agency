"""Pydantic request/response models for `api/v1/routers/cash_handover.py`.

Like all schemas, `uuid`/`datetime` are real imports.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class DeclareCashHandoverRequest(BaseModel):
    driver_id: uuid.UUID
    route_id: uuid.UUID
    actual_amount: Decimal = Field(ge=0)


class CashHandoverResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    handover_number: str | None = None
    driver_id: uuid.UUID
    route_id: uuid.UUID
    expected_amount: Decimal
    actual_amount: Decimal
    shortfall: Decimal
    declared_by: uuid.UUID
    declared_at: datetime


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
    handover: CashHandoverResponse | None = None
