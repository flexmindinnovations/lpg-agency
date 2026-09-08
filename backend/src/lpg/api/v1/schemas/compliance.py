"""Pydantic request/response models for `api/v1/routers/compliance.py`
(Weighment Part 1 — scale registry; TDT rating — Phase 20 subsystem 2)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class RegisterScaleRequest(BaseModel):
    warehouse_id: uuid.UUID
    asset_tag: str = Field(min_length=1)
    least_count_grams: int = Field(gt=0)
    certificate_ref: str = Field(min_length=1)
    certificate_expiry_date: date
    make: str | None = None
    model: str | None = None


class ReplaceScaleCertificateRequest(BaseModel):
    certificate_ref: str = Field(min_length=1)
    certificate_expiry_date: date


class SetScaleStatusRequest(BaseModel):
    status: str


class ScaleResponse(BaseModel):
    id: uuid.UUID
    warehouse_id: uuid.UUID
    asset_tag: str
    make: str | None
    model: str | None
    least_count_grams: int
    certificate_url: str | None
    certificate_expiry_date: date
    status: str
    is_expired: bool


class ScaleListResponse(BaseModel):
    items: list[ScaleResponse]
    total: int


class RecordWeighmentRequest(BaseModel):
    scale_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    total_cylinders_in_batch: int = Field(gt=0)
    cylinders_checked: int = Field(gt=0)
    underweight_cylinder_count: int = Field(ge=0)


class WeighmentRecordResponse(BaseModel):
    id: uuid.UUID
    scale_id: uuid.UUID
    context: str
    reference_type: str
    reference_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    total_cylinders_in_batch: int
    cylinders_checked: int
    underweight_cylinder_count: int
    tolerance_grams_applied: int
    result: str
    recorded_by: uuid.UUID
    recorded_at: datetime


class WeighmentRecordListResponse(BaseModel):
    items: list[WeighmentRecordResponse]


class TdtBandDistributionResponse(BaseModel):
    stars: int
    order_count: int


class TdtQuarterlyRatingResponse(BaseModel):
    """`overall_stars` is `null` when there is no delivered-order data for
    the requested period — no `tdt_star_rating_bands` configured yet, or
    zero orders delivered in the window — never a guessed value."""

    overall_stars: int | None
    total_orders: int
    distribution: list[TdtBandDistributionResponse]
    quarter_start: date
    quarter_end: date
