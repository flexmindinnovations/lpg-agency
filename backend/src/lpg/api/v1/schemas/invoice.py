"""Pydantic request/response models for `api/v1/routers/invoice.py`.

Like all schemas, `uuid`/`datetime` are real imports.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003
from decimal import Decimal  # noqa: TC003

from pydantic import BaseModel, ConfigDict


class InvoiceLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    line_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    quantity: int
    unit_price: Decimal
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal


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


class InvoicePageResponse(BaseModel):
    items: list[InvoiceResponse]
    total: int
    page: int
    page_size: int
