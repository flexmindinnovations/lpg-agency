"""Pydantic request/response models for `api/v1/routers/customer.py`.

`uuid`/`datetime`/`Decimal` are real imports, not `TYPE_CHECKING`-guarded:
with `from __future__ import annotations`, Pydantic resolves each model's
field types via `typing.get_type_hints()` at class-definition time to build
its validation schema — the same footgun `models/tenant.py`'s module
docstring documents for SQLAlchemy's `Mapped[...]`, here for Pydantic
instead (see `schemas/admin.py`'s identical note).
"""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003
from decimal import Decimal  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field


class CustomerAddressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    address_line: str
    latitude: Decimal | None
    longitude: Decimal | None
    is_primary: bool


class KycDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    doc_type: str
    doc_reference: str
    verification_status: str
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
    consumer_number: str
    full_name: str
    phone_number: str
    customer_type: str
    kyc_status: str
    status: str
    lpg_subsidy_id: str | None
    addresses: list[CustomerAddressResponse]


class RegisterCustomerRequest(BaseModel):
    branch_id: uuid.UUID
    consumer_number: str = Field(min_length=1, max_length=50)
    full_name: str = Field(min_length=1, max_length=200)
    phone_number: str = Field(min_length=1, max_length=20)
    customer_type: str = "domestic"
    # The nationally-standardized 17-digit LPG ID (subsidy/KYC/bank-linking)
    # — distinct from consumer_number, see `domain/customer/customer.py`.
    lpg_subsidy_id: str | None = Field(default=None, pattern=r"^\d{17}$")
    address_line: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None


class UpdateCustomerProfileRequest(BaseModel):
    branch_id: uuid.UUID
    full_name: str = Field(min_length=1, max_length=200)
    phone_number: str = Field(min_length=1, max_length=20)
    customer_type: str
    status: str
    lpg_subsidy_id: str | None = Field(default=None, pattern=r"^\d{17}$")


class NextConsumerNumberResponse(BaseModel):
    consumer_number: str


class AddCustomerAddressRequest(BaseModel):
    address_line: str = Field(min_length=1)
    latitude: Decimal | None = None
    longitude: Decimal | None = None


class SubmitKycDocumentRequest(BaseModel):
    doc_type: str = Field(min_length=1, max_length=50)
    doc_reference: str = Field(min_length=1)


class VerifyKycDocumentRequest(BaseModel):
    status: str = Field(pattern="^(verified|rejected)$")


class CustomerPageResponse(BaseModel):
    items: list[CustomerResponse]
    total: int


class KycDocumentListResponse(BaseModel):
    items: list[KycDocumentResponse]
