"""Pydantic models for `api/v1/routers/payment_profile.py` (ADR-066)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class PaymentProfileResponse(BaseModel):
    account_holder: str = ""
    bank_name: str = ""
    account_number: str = ""
    ifsc: str = ""
    branch: str = ""
    upi_id: str = ""
    upi_payee_name: str = ""
    invoice_footer_note: str = ""
    has_bank_details: bool = False
    has_upi: bool = False


class SetPaymentProfileRequest(BaseModel):
    account_holder: str = Field(default="", max_length=120)
    bank_name: str = Field(default="", max_length=120)
    account_number: str = Field(default="", max_length=30)
    ifsc: str = Field(default="", max_length=11)
    branch: str = Field(default="", max_length=120)
    upi_id: str = Field(default="", max_length=100)
    upi_payee_name: str = Field(default="", max_length=100)
    invoice_footer_note: str = Field(default="", max_length=300)


class UpiQrResponse(BaseModel):
    """What a payer needs to pay by UPI: the deep link, and the same link as
    a QR image the app can show as is.
    """

    upi_uri: str
    upi_id: str
    payee_name: str
    amount: Decimal
    order_id: uuid.UUID | None = None
    invoice_id: uuid.UUID | None = None
    #: PNG, base64 encoded.
    qr_png_base64: str
