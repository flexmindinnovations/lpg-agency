from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class DailySalesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sale_date: date
    branch_id: uuid.UUID | None
    total_invoices: int
    total_revenue: Decimal
    total_tax: Decimal


class GstFilingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    filing_period: str
    total_gst: Decimal


class CustomerConsumptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    customer_id: uuid.UUID
    avg_refill_interval_days: float


class DriverPerformanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    driver_id: uuid.UUID
    date: date
    total_stops: int
    delivered_stops: int
    cash_accuracy: float
