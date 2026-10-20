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
    #: GST snapshot at issue (BR-16). `None` only on invoices issued before
    #: GST was configured per cylinder type.
    hsn_code: str | None = None
    gst_rate_percent: Decimal | None = None
    #: `supply` (cylinders delivered) or `cancellation_charge` (DO-14).
    kind: str = "supply"
    description: str | None = None
    cgst_amount: Decimal = Decimal("0")
    sgst_amount: Decimal = Decimal("0")
    igst_amount: Decimal = Decimal("0")


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    payment_id: uuid.UUID
    method: str
    amount: Decimal
    collected_by: uuid.UUID
    collected_at: datetime
    reference: str | None = None


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    invoice_id: uuid.UUID
    invoice_number: str | None = None
    tenant_id: uuid.UUID
    customer_id: uuid.UUID
    customer_consumer_number: str | None = None
    order_id: uuid.UUID
    order_number: str | None = None
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
    balance_due: Decimal = Decimal("0")
    customer_name: str | None = None
    customer_gstin: str | None = None
    #: GST state codes; CGST+SGST when they match, IGST when they differ.
    supplier_state_code: str | None = None
    place_of_supply_state_code: str | None = None
    is_inter_state: bool = False
    cgst_amount: Decimal = Decimal("0")
    sgst_amount: Decimal = Decimal("0")
    igst_amount: Decimal = Decimal("0")


class InvoicePageResponse(BaseModel):
    items: list[InvoiceResponse]
    total: int
    page: int
    page_size: int


class RecordPaymentRequest(BaseModel):
    #: `cash`, `upi`, `card`, `cheque` or `bank_transfer` when recorded by
    #: staff; the server rejects anything else.
    method: str
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    #: UPI transaction id, cheque number or bank UTR. Required for cheque
    #: and bank transfer.
    reference: str | None = Field(default=None, max_length=100)


class RequestRefundRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    reason: str = Field(min_length=1)


class CreditNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    credit_note_number: str | None = None
    invoice_id: uuid.UUID
    amount: Decimal
    reason: str
    requested_by: uuid.UUID
    requested_at: datetime
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    is_approved: bool


class UninvoicedOrderResponse(BaseModel):
    """An order that should have an invoice but does not yet — usually
    because GST was not configured when it was delivered or cancelled.
    """

    order_id: uuid.UUID
    order_number: str | None
    customer_id: uuid.UUID
    customer_name: str
    status: str
    occurred_at: datetime
    order_total: Decimal | None
    cancellation_charge: Decimal | None


class IssueInvoiceRequest(BaseModel):
    order_id: uuid.UUID
