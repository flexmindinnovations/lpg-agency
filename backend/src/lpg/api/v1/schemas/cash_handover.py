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
    driver_id: uuid.UUID
    route_id: uuid.UUID
    expected_amount: Decimal
    actual_amount: Decimal
    shortfall: Decimal
    declared_by: uuid.UUID
    declared_at: datetime
