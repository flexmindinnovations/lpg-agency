"""Pydantic request/response models for `api/v1/routers/delivery.py`.

`uuid`/`date` are real imports, not `TYPE_CHECKING`-guarded: with
`from __future__ import annotations`, Pydantic resolves each model's field
types via `typing.get_type_hints()` at class-definition time to build its
validation schema — see `schemas/customer.py`'s identical note.

Driver/Vehicle responses deliberately omit `created_at`/`updated_at`: the
`Driver`/`Vehicle` domain aggregates don't carry audit timestamps (only
`version`, for optimistic concurrency), so a response field for them would
have to be fabricated at the API layer rather than reflect the real
persisted value — the same reason `CustomerResponse` omits them.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import date  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field

# ==========================================================================
# Driver Schemas
# ==========================================================================


class DriverResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    branch_id: uuid.UUID
    identity_user_id: uuid.UUID | None
    employee_code: str
    license_number: str
    license_expiry_date: date | None
    status: str
    version: int


class DriverPageResponse(BaseModel):
    items: list[DriverResponse]
    total: int
    page: int
    page_size: int


class RegisterDriverRequest(BaseModel):
    branch_id: uuid.UUID
    employee_code: str = Field(min_length=1, max_length=50)
    license_number: str = Field(min_length=1, max_length=100)
    license_expiry_date: date | None = None
    identity_user_id: uuid.UUID | None = None


class UpdateDriverStatusRequest(BaseModel):
    status: str


class UpdateDriverLicenseRequest(BaseModel):
    license_number: str = Field(min_length=1, max_length=100)
    license_expiry_date: date | None = None


# ==========================================================================
# Vehicle Schemas
# ==========================================================================


class VehicleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    branch_id: uuid.UUID
    registration_number: str
    make: str
    model: str
    ownership_type: str
    capacity_units: int
    status: str
    version: int


class VehiclePageResponse(BaseModel):
    items: list[VehicleResponse]
    total: int
    page: int
    page_size: int


class RegisterVehicleRequest(BaseModel):
    branch_id: uuid.UUID
    registration_number: str = Field(min_length=1, max_length=20)
    make: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=100)
    ownership_type: str = "owned"
    capacity_units: int = Field(ge=1)


class UpdateVehicleStatusRequest(BaseModel):
    status: str
