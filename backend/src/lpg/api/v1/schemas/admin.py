"""Pydantic request/response models for `api/v1/routers/admin.py`.

`datetime`/`Decimal` are real imports, not `TYPE_CHECKING`-guarded: with
`from __future__ import annotations`, Pydantic resolves each model's field
types via `typing.get_type_hints()` at class-definition time to build its
validation schema — the same footgun `models/tenant.py`'s module docstring
documents for SQLAlchemy's `Mapped[...]`, here for Pydantic instead.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from decimal import Decimal  # noqa: TC003
from typing import Any

from pydantic import BaseModel, EmailStr, Field

# -- Tenant -----------------------------------------------------------------


class TenantResponse(BaseModel):
    id: str
    name: str
    slug: str
    status: str
    subscription_plan: str
    primary_contact_email: str
    country: str


class RenameTenantRequest(BaseModel):
    name: str = Field(min_length=1)


# -- Branch -------------------------------------------------------------------


class BranchResponse(BaseModel):
    id: str
    name: str
    region: str | None


class CreateBranchRequest(BaseModel):
    name: str = Field(min_length=1)
    region: str | None = None


class RenameBranchRequest(BaseModel):
    name: str = Field(min_length=1)


class SetBranchRegionRequest(BaseModel):
    region: str | None = None


# -- Warehouse ----------------------------------------------------------------


class WarehouseResponse(BaseModel):
    id: str
    branch_id: str
    name: str
    address_line: str


class CreateWarehouseRequest(BaseModel):
    branch_id: str
    name: str = Field(min_length=1)
    address_line: str = Field(min_length=1)


class RenameWarehouseRequest(BaseModel):
    name: str = Field(min_length=1)


class RelocateWarehouseRequest(BaseModel):
    address_line: str = Field(min_length=1)


# -- Cylinder Type --------------------------------------------------------------


class CylinderTypeResponse(BaseModel):
    id: str
    name: str
    weight_kg: Decimal
    is_active: bool


class CreateCylinderTypeRequest(BaseModel):
    name: str = Field(min_length=1)
    weight_kg: Decimal = Field(gt=0)


class RenameCylinderTypeRequest(BaseModel):
    name: str = Field(min_length=1)


class AdjustCylinderTypeWeightRequest(BaseModel):
    weight_kg: Decimal = Field(gt=0)


class SetCylinderTypeActiveRequest(BaseModel):
    is_active: bool


# -- Tenant Configuration -------------------------------------------------------


class TenantConfigurationResponse(BaseModel):
    id: str
    config_key: str
    config_value: Any
    effective_from: datetime


class SetTenantConfigurationRequest(BaseModel):
    config_key: str
    config_value: Any
    effective_from: datetime | None = None


# -- Price List -----------------------------------------------------------------


class PriceListEntryResponse(BaseModel):
    id: str
    cylinder_type_id: str
    customer_type: str
    branch_id: str | None
    price: Decimal
    effective_from: datetime


class SetPriceRequest(BaseModel):
    cylinder_type_id: str
    customer_type: str
    price: Decimal = Field(gt=0)
    branch_id: str | None = None
    effective_from: datetime | None = None


# -- Feature Flags ----------------------------------------------------------------


class FeatureFlagResponse(BaseModel):
    key: str
    description: str
    is_enabled_by_default: bool
    rollout_percentage: int | None
    starts_at: datetime | None
    ends_at: datetime | None


class CreateFeatureFlagRequest(BaseModel):
    key: str = Field(min_length=1)
    description: str = Field(min_length=1)
    is_enabled_by_default: bool = False
    rollout_percentage: int | None = Field(default=None, ge=0, le=100)


class SetFeatureFlagEnabledByDefaultRequest(BaseModel):
    enabled: bool


class SetFeatureFlagRolloutPercentageRequest(BaseModel):
    rollout_percentage: int | None = Field(default=None, ge=0, le=100)


class ScheduleFeatureFlagRequest(BaseModel):
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class SetFeatureFlagOverrideRequest(BaseModel):
    enabled: bool


class FeatureFlagOverrideResponse(BaseModel):
    flag_key: str
    is_enabled: bool


class FeatureFlagEnabledResponse(BaseModel):
    key: str
    enabled: bool


# -- Staff Users --------------------------------------------------------------------


class StaffUserResponse(BaseModel):
    id: str
    email: str | None
    role: str
    branch_id: str | None
    is_active: bool


class InviteStaffUserRequest(BaseModel):
    email: EmailStr
    role: str
    branch_id: str | None = None


class ReassignRoleRequest(BaseModel):
    new_role: str


class UpdateStaffUserPermissionsRequest(BaseModel):
    permission_codes: list[str]


# -- Audit Log ----------------------------------------------------------------------


class AuditLogEntryResponse(BaseModel):
    id: str
    actor_id: str | None
    actor_display_name: str | None
    entity_name: str
    entity_id: str | None
    entity_display_name: str | None
    action: str
    performed_at: datetime
    correlation_id: str | None
    before_state: dict[str, Any] | None
    after_state: dict[str, Any] | None


class AuditLogPageResponse(BaseModel):
    items: list[AuditLogEntryResponse]
    next_cursor: str | None
