from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class DailySalesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sale_date: date
    branch_id: uuid.UUID | None
    branch_name: str | None = None
    total_invoices: int
    taxable_value: Decimal = Decimal("0")
    total_revenue: Decimal
    total_tax: Decimal


class GstFilingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    filing_period: str
    total_gst: Decimal


class CustomerConsumptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    customer_id: uuid.UUID
    customer_name: str
    avg_refill_interval_days: float


class DriverPerformanceResponse(BaseModel):
    driver_id: uuid.UUID
    driver_name: str
    employee_code: str | None = None
    branch_name: str | None = None
    date: date
    total_stops: int
    delivered_stops: int
    failed_stops: int = 0
    cash_expected: Decimal = Decimal("0")
    cash_handed_over: Decimal | None = None
    #: Handed over / expected, as a ratio. `None` until a handover is
    #: declared, or when no cash was due.
    cash_accuracy: float | None = None


class GstTaxTotalsResponse(BaseModel):
    taxable_value: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    total_tax: Decimal


class Gstr1InvoiceRowResponse(BaseModel):
    invoice_id: uuid.UUID
    invoice_number: str | None
    invoice_date: datetime
    customer_name: str
    customer_gstin: str | None
    invoice_value: Decimal
    place_of_supply: str
    rate_percent: Decimal
    totals: GstTaxTotalsResponse


class Gstr1B2csRowResponse(BaseModel):
    place_of_supply: str
    rate_percent: Decimal
    totals: GstTaxTotalsResponse


class Gstr1HsnRowResponse(BaseModel):
    hsn_code: str
    rate_percent: Decimal
    #: Unit quantity code — cylinders are counted in numbers (NOS).
    uqc: str = "NOS"
    quantity: int
    totals: GstTaxTotalsResponse


class Gstr1ReportResponse(BaseModel):
    """Outward supplies for a period, laid out like GSTR-1 (DA-12)."""

    start_date: date
    end_date: date
    invoice_count: int
    b2b: list[Gstr1InvoiceRowResponse]
    b2cl: list[Gstr1InvoiceRowResponse]
    b2cs: list[Gstr1B2csRowResponse]
    hsn: list[Gstr1HsnRowResponse]
    totals: GstTaxTotalsResponse
