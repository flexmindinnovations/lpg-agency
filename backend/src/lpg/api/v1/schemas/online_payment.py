"""Pydantic models for `api/v1/routers/online_payment.py` (ADR-053).

Like all schemas, `uuid`/`datetime` are real imports.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

OnlinePaymentStatus = Literal["created", "paid", "expired", "cancelled"]


class OnlinePaymentResponse(BaseModel):
    online_payment_id: uuid.UUID
    order_id: uuid.UUID
    invoice_id: uuid.UUID | None
    amount: Decimal
    currency: str
    status: OnlinePaymentStatus
    provider: str
    payment_url: str = Field(description="Hosted checkout page to send the customer to.")
    expires_at: datetime | None
    paid_at: datetime | None
    payment_method: str | None
    applied_to_invoice: bool
    created_at: datetime


class OnlinePaymentListResponse(BaseModel):
    items: list[OnlinePaymentResponse]


class WebhookAck(BaseModel):
    received: bool
