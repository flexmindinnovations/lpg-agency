from __future__ import annotations

from datetime import datetime  # noqa: TC003
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class TenantHeader(BaseModel):
    """The supplier block of a tax invoice (CGST Rules, rule 46)."""

    model_config = ConfigDict(frozen=True)
    agency_name: str
    address_line_1: str = ""
    address_line_2: str = ""
    city: str = ""
    state: str = ""
    pincode: str = ""
    state_code: str = ""
    gstin: str = ""
    phone: str = ""


class CustomerInfo(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    consumer_number: str = ""
    address: str = ""
    phone: str = ""
    #: Set only for a GST-registered (B2B) customer.
    gstin: str = ""


class PrintLineItem(BaseModel):
    model_config = ConfigDict(frozen=True)
    description: str
    hsn_code: str = ""
    gst_rate_percent: Decimal | None = None
    quantity: int
    unit_price: Decimal
    subtotal: Decimal
    cgst_amount: Decimal = Decimal("0.00")
    sgst_amount: Decimal = Decimal("0.00")
    igst_amount: Decimal = Decimal("0.00")
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
    cgst_amount: Decimal = Decimal("0.00")
    sgst_amount: Decimal = Decimal("0.00")
    igst_amount: Decimal = Decimal("0.00")
    tax_amount: Decimal
    total_amount: Decimal
    total_in_words: str = ""
    #: "36-Telangana" style, as GST invoices state the place of supply.
    place_of_supply: str = ""
    is_inter_state: bool = False
    amount_paid: Decimal = Decimal("0.00")
    balance_due: Decimal = Decimal("0.00")
    payment_status: str
    issued_at: datetime
    qr_code_data: str = ""  # The string to encode as QR — typically a URL or reference

    @property
    def prices_include_gst(self) -> bool:
        """True when the line rates are GST-inclusive (`prices_include_gst`):
        every taxed line's total is exactly rate x quantity. Read from the
        stored amounts, so a reprint states what was actually invoiced.
        """
        taxed = [item for item in self.line_items if item.tax_amount > 0]
        return bool(taxed) and all(
            item.unit_price * item.quantity == item.total_amount for item in taxed
        )
