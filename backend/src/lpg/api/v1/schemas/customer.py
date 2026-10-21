"""Pydantic request/response models for `api/v1/routers/customer.py`.

`uuid`/`datetime`/`Decimal` are real imports, not `TYPE_CHECKING`-guarded:
with `from __future__ import annotations`, Pydantic resolves each model's
field types via `typing.get_type_hints()` at class-definition time to build
its validation schema — the same footgun `models/tenant.py`'s module
docstring documents for SQLAlchemy's `Mapped[...]`, here for Pydantic
instead (see `schemas/admin.py`'s identical note).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CustomerType = Literal["domestic", "commercial", "industrial", "government"]
CustomerStatus = Literal[
    "onboarding", "pending_approval", "active", "inactive", "blocked", "closed"
]
AddressType = Literal["delivery", "billing", "both"]
KycDocumentType = Literal["aadhaar", "pan", "voter_id", "driving_license", "passport"]

#: Indian PIN code — 6 digits, never starting with 0. The domain re-checks
#: it (`domain/customer/identifiers.py`); this gives API clients a 422 with
#: the field named before anything else runs.
_PINCODE = r"^\s*[1-9]\d{5}\s*$"


class CustomerAddressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    line_1: str
    line_2: str | None
    landmark: str | None
    area: str | None
    city: str | None
    district: str | None
    state: str | None
    pincode: str | None
    address_type: str
    latitude: Decimal | None
    longitude: Decimal | None
    is_primary: bool


class KycDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    doc_type: str
    document_number: str
    file_url: str | None
    issue_date: date | None
    expiry_date: date | None
    verification_status: str
    rejection_reason: str | None
    verified_at: datetime | None


class CustomerResponse(BaseModel):
    """The general customer profile — deliberately excludes `kyc_documents`.

    KYC documents are more sensitive PII than the rest of this profile
    (`docs/data/17-api-security.md` §10) and are gated by their own
    `kyc:read` permission, distinct from `customers:read` — see
    `GET /customers/{id}/kyc`. `kyc_status` stays here: it is a coarse
    account-status field on `customer.customer` itself, not a document.
    """

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    branch_id: uuid.UUID
    consumer_number: str | None
    full_name: str
    phone_number: str
    contact_person: str | None
    alternate_mobile: str | None
    email: str | None
    date_of_birth: date | None
    customer_type: str
    kyc_status: str
    status: str
    lpg_subsidy_id: str | None
    #: GST number of a commercial/industrial/government customer — printed on
    #: B2B tax invoices. Always `None` for domestic customers.
    gstin: str | None = None
    addresses: list[CustomerAddressResponse]


class RegisterCustomerRequest(BaseModel):
    branch_id: uuid.UUID
    consumer_number: str | None = Field(default=None, max_length=50)
    full_name: str = Field(min_length=1, max_length=200)
    phone_number: str = Field(min_length=1, max_length=20)
    contact_person: str | None = Field(default=None, max_length=200)
    alternate_mobile: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=200)
    date_of_birth: date | None = None
    customer_type: CustomerType = "domestic"
    # The nationally-standardized 17-digit LPG ID (subsidy/KYC/bank-linking)
    # — distinct from consumer_number, see `domain/customer/customer.py`.
    lpg_subsidy_id: str | None = Field(default=None, pattern=r"^\d{17}$")
    gstin: str | None = Field(default=None, max_length=20)

    line_1: str | None = None
    line_2: str | None = None
    landmark: str | None = None
    area: str | None = None
    city: str | None = None
    district: str | None = None
    state: str | None = None
    pincode: str | None = Field(default=None, pattern=_PINCODE)
    address_type: AddressType | None = None
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)


class UpdateCustomerProfileRequest(BaseModel):
    branch_id: uuid.UUID
    full_name: str = Field(min_length=1, max_length=200)
    phone_number: str = Field(min_length=1, max_length=20)
    contact_person: str | None = Field(default=None, max_length=200)
    alternate_mobile: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=200)
    date_of_birth: date | None = None
    customer_type: CustomerType
    status: CustomerStatus
    lpg_subsidy_id: str | None = Field(default=None, pattern=r"^\d{17}$")
    gstin: str | None = Field(default=None, max_length=20)


class NextConsumerNumberResponse(BaseModel):
    consumer_number: str


class AddCustomerAddressRequest(BaseModel):
    line_1: str = Field(min_length=1, max_length=500)
    line_2: str | None = Field(default=None, max_length=500)
    landmark: str | None = Field(default=None, max_length=200)
    area: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    pincode: str = Field(pattern=_PINCODE)
    address_type: AddressType = "delivery"
    #: Optional map pin. Both or neither.
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)


class UpdateCustomerAddressRequest(BaseModel):
    line_1: str = Field(min_length=1, max_length=500)
    line_2: str | None = Field(default=None, max_length=500)
    landmark: str | None = Field(default=None, max_length=200)
    area: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    pincode: str = Field(pattern=_PINCODE)
    address_type: AddressType = "delivery"
    #: Optional map pin. Both or neither.
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)


class SubmitKycDocumentRequest(BaseModel):
    doc_type: KycDocumentType
    document_number: str = Field(min_length=1, max_length=30)
    file_url: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None


class VerifyKycDocumentRequest(BaseModel):
    status: str = Field(pattern="^(verified|rejected)$")
    rejection_reason: str | None = None


class ApproveCustomerRequest(BaseModel):
    consumer_number: str | None = Field(default=None, max_length=50)


class CustomerPageResponse(BaseModel):
    items: list[CustomerResponse]
    total: int


class RefillDueCustomerResponse(BaseModel):
    """One row of the AI Operational Intelligence refill-due read model
    (`GET /customers/refill-due`, Horizon 1 Stage 2) — a heuristic
    prediction, not a guarantee; `model_version` on the underlying
    `ai.prediction` row is `refill_heuristic_v1`."""

    customer_id: uuid.UUID
    full_name: str
    phone_number: str
    branch_id: uuid.UUID
    refill_due_date: date
    interval_days: float
    last_delivered_at: date


class RefillDueCustomerListResponse(BaseModel):
    items: list[RefillDueCustomerResponse]
    total: int


class KycDocumentListResponse(BaseModel):
    items: list[KycDocumentResponse]


class KycAttachmentResponse(BaseModel):
    """A pre-uploaded KYC document image blob ref — see
    `upload_kyc_attachment`'s docstring for why this is a separate,
    customer-agnostic endpoint from `POST /{customer_id}/kyc`.
    """

    blob_ref: str


class RecognizeKycDocumentRequest(BaseModel):
    blob_ref: str = Field(min_length=1)


class RecognizeKycDocumentResponse(BaseModel):
    """Result of the backend OCR "second pass" — see
    `RecognizeKycDocumentUseCase`'s docstring for why this exists.

    The address_* fields are a best-effort split of the Aadhaar address
    block (see `kyc_document_parser.py::_parse_address`) — freeform,
    unlabeled text with no fixed structure, so these are meaningfully less
    reliable than doc_type/document_number/full_name/date_of_birth. The
    Address step's fields stay required and editable regardless of what
    auto-fills here.
    """

    doc_type: str | None
    document_number: str | None
    full_name: str | None
    date_of_birth: date | None
    confidence: float
    address_line_1: str | None
    address_line_2: str | None
    address_landmark: str | None
    address_area: str | None
    address_city: str | None
    address_district: str | None
    address_state: str | None
    address_pincode: str | None
