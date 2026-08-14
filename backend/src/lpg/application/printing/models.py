from __future__ import annotations

from datetime import datetime  # noqa: TC003
from decimal import Decimal  # noqa: TC003

from pydantic import BaseModel, ConfigDict


class TenantHeader(BaseModel):
    model_config = ConfigDict(frozen=True)
    agency_name: str
    address_line_1: str = ""
    address_line_2: str = ""
    city: str = ""
    state: str = ""
    pincode: str = ""
    gstin: str = ""
    phone: str = ""


class CustomerInfo(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    consumer_number: str = ""
    address: str = ""
    phone: str = ""


class PrintLineItem(BaseModel):
    model_config = ConfigDict(frozen=True)
    description: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal


class InvoicePrintPayload(BaseModel):
    """Fully-resolved print payload for an invoice.

    Assembled by the application use case, not by the printing engine.
    The engine only renders — it never queries data.
    """

    model_config = ConfigDict(frozen=True)

    invoice_number: str
    tenant_header: TenantHeader
    customer: CustomerInfo
    line_items: list[PrintLineItem]
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    tax_rate_percent: Decimal = Decimal("18.0")
    payment_status: str
    issued_at: datetime
    qr_code_data: str = ""  # The string to encode as QR — typically a URL or reference
