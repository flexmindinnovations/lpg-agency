"""Pydantic request/response models for `api/v1/routers/compliance.py`
(Weighment Part 1 — scale registry)."""

from __future__ import annotations

import uuid
from datetime import date

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
