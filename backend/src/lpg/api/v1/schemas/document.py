"""Schemas for the generic `/documents` endpoints — pre-upload + server-side
OCR of a scanned document, shared by customer KYC and driver/vehicle
compliance."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class DocumentAttachmentResponse(BaseModel):
    """A pre-uploaded document image blob ref, staged under a tenant-scoped
    key before the owning record exists."""

    blob_ref: str


class RecognizeComplianceDocumentRequest(BaseModel):
    blob_ref: str = Field(min_length=1)
    doc_kind: Literal["driving_licence", "vehicle_rc"]


class RecognizeComplianceDocumentResponse(BaseModel):
    """Result of the OCR "second pass" for a DL or RC image. Only the fields
    relevant to `doc_kind` are populated; every one is a reviewable head start
    the caller edits before saving, never written straight through."""

    doc_kind: Literal["driving_licence", "vehicle_rc"]
    confidence: float
    document_number: str | None = None
    holder_name: str | None = None
    # Driving licence
    date_of_birth: date | None = None
    valid_till: date | None = None
    transport_valid_till: date | None = None
    vehicle_classes: list[str] = Field(default_factory=list)
    # Vehicle RC
    registration_number: str | None = None
    registration_date: date | None = None
    fitness_upto: date | None = None
    insurance_upto: date | None = None
    chassis_number: str | None = None
    engine_number: str | None = None
    fuel_type: str | None = None
    maker_model: str | None = None
