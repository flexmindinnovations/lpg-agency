"""Schemas for the generic `/documents` endpoints — pre-upload + server-side
OCR of a scanned document, shared by customer KYC and driver/vehicle
compliance."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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


# ==========================================================================
# Compliance document CRUD
# ==========================================================================

ComplianceOwnerType = Literal["driver", "vehicle"]


class AddComplianceDocumentRequest(BaseModel):
    doc_type: str
    document_number: str = Field(min_length=1)
    file_ref: str = Field(min_length=1)
    issue_date: date | None = None
    expiry_date: date | None = None


class ReplaceComplianceDocumentRequest(BaseModel):
    document_number: str = Field(min_length=1)
    file_ref: str = Field(min_length=1)
    issue_date: date | None = None
    expiry_date: date | None = None


class VerifyComplianceDocumentRequest(BaseModel):
    status: Literal["verified", "rejected"]
    rejection_reason: str | None = None


class ComplianceDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_type: str
    owner_id: uuid.UUID
    doc_type: str
    document_number: str
    file_url: str | None
    issue_date: date | None
    expiry_date: date | None
    verification_status: str
    rejection_reason: str | None
    verified_at: datetime | None


class ComplianceDocumentListResponse(BaseModel):
    items: list[ComplianceDocumentResponse]
    total: int
