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

from pydantic import BaseModel, ConfigDict, Field


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
    customer_type: str = "domestic"
    # The nationally-standardized 17-digit LPG ID (subsidy/KYC/bank-linking)
    # — distinct from consumer_number, see `domain/customer/customer.py`.
    lpg_subsidy_id: str | None = Field(default=None, pattern=r"^\d{17}$")

    line_1: str | None = None
    line_2: str | None = None
    landmark: str | None = None
    area: str | None = None
    city: str | None = None
    district: str | None = None
    state: str | None = None
    pincode: str | None = None
    address_type: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None


class UpdateCustomerProfileRequest(BaseModel):
    branch_id: uuid.UUID
    full_name: str = Field(min_length=1, max_length=200)
    phone_number: str = Field(min_length=1, max_length=20)
    contact_person: str | None = Field(default=None, max_length=200)
    alternate_mobile: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=200)
    date_of_birth: date | None = None
    customer_type: str
    status: str
    lpg_subsidy_id: str | None = Field(default=None, pattern=r"^\d{17}$")


class NextConsumerNumberResponse(BaseModel):
    consumer_number: str


class AddCustomerAddressRequest(BaseModel):
    line_1: str = Field(min_length=1)
    line_2: str | None = None
    landmark: str | None = None
    area: str | None = None
    city: str | None = None
    district: str | None = None
    state: str | None = None
    pincode: str | None = None
    address_type: str = "delivery"
    latitude: Decimal | None = None
    longitude: Decimal | None = None


class SubmitKycDocumentRequest(BaseModel):
    doc_type: str = Field(min_length=1, max_length=50)
    document_number: str = Field(min_length=1)
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


class KycDocumentListResponse(BaseModel):
    items: list[KycDocumentResponse]
