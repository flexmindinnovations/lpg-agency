"""Pydantic request/response models for `api/v1/routers/invoice.py`.

Like all schemas, `uuid`/`datetime` are real imports.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class InvoiceLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    line_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    quantity: int
    unit_price: Decimal
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    payment_id: uuid.UUID
    method: str
    amount: Decimal
    collected_by: uuid.UUID
    collected_at: datetime


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    invoice_id: uuid.UUID
    tenant_id: uuid.UUID
    customer_id: uuid.UUID
    order_id: uuid.UUID
    status: str
    issued_at: datetime
    lines: list[InvoiceLineResponse]
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    version: int
    # Additive (R10) — a pre-existing client built against this schema
    # before payments existed simply ignores these two fields.
    payments: list[PaymentResponse] = Field(default_factory=list)
    amount_paid: Decimal = Decimal("0")


class InvoicePageResponse(BaseModel):
    items: list[InvoiceResponse]
    total: int
    page: int
    page_size: int


class RecordPaymentRequest(BaseModel):
    method: str
    amount: Decimal = Field(gt=0)


class RequestRefundRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    reason: str = Field(min_length=1)


class CreditNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_id: uuid.UUID
    amount: Decimal
    reason: str
    requested_by: uuid.UUID
    requested_at: datetime
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    is_approved: bool
