"""Pydantic request/response models for `api/v1/routers/admin.py`.

`datetime`/`Decimal` are real imports, not `TYPE_CHECKING`-guarded: with
`from __future__ import annotations`, Pydantic resolves each model's field
types via `typing.get_type_hints()` at class-definition time to build its
validation schema — the same footgun `models/tenant.py`'s module docstring
documents for SQLAlchemy's `Mapped[...]`, here for Pydantic instead.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field

from lpg.domain.tenant.tenant import (
    NAME_MAX_LENGTH,
    SLUG_MAX_LENGTH,
    SLUG_MIN_LENGTH,
    SLUG_PATTERN,
)

# -- Tenant -----------------------------------------------------------------


class TenantResponse(BaseModel):
    id: str
    name: str
    slug: str
    status: str
    subscription_plan: str
    primary_contact_email: str
    country: str


class CreateAgencyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=NAME_MAX_LENGTH)
    # Also the agency's future subdomain — a lowercase DNS label
    # (`domain/tenant/tenant.py` owns the rules; this only mirrors them so a
    # bad value is a field-level 422 instead of a generic 409).
    slug: str = Field(min_length=SLUG_MIN_LENGTH, max_length=SLUG_MAX_LENGTH, pattern=SLUG_PATTERN)
    primary_contact_email: EmailStr
    admin_email: EmailStr
    country: str = Field(default="IN", pattern=r"^[A-Za-z]{2}$")
    subscription_plan: str = Field(default="standard", min_length=1, max_length=50)


class CreateAgencyResponse(BaseModel):
    tenant: TenantResponse
    admin_user_id: str
    admin_email: str
    #: One-time link for the first admin to set their password. Returned once
    #: and never stored (only its hash is) — email delivery is not wired up
    #: yet, so the Super Admin passes it on.
    setup_path: str
    setup_token_expires_at: datetime


class AddAgencyAdminRequest(BaseModel):
    email: EmailStr


class AgencyUserSetupResponse(BaseModel):
    """A user plus the one-time link to set their password. The raw token is
    returned once and never stored (only its hash is)."""

    user_id: str
    email: str | None
    role: str
    #: `/reset-password?token=...` - prefix it with the site's origin.
    setup_path: str
    setup_token_expires_at: datetime


class RenameTenantRequest(BaseModel):
    name: str = Field(min_length=1)


# -- Branch -------------------------------------------------------------------


class BranchResponse(BaseModel):
    id: str
    name: str
    region: str | None
    is_active: bool


class CreateBranchRequest(BaseModel):
    name: str = Field(min_length=1)
    region: str | None = None


class RenameBranchRequest(BaseModel):
    name: str = Field(min_length=1)


class SetBranchRegionRequest(BaseModel):
    region: str | None = None


class SetBranchActiveRequest(BaseModel):
    is_active: bool


# -- Warehouse ----------------------------------------------------------------


class WarehouseResponse(BaseModel):
    id: str
    branch_id: str
    name: str
    address_line: str
    is_active: bool


class CreateWarehouseRequest(BaseModel):
    branch_id: str
    name: str = Field(min_length=1)
    address_line: str = Field(min_length=1)


class RenameWarehouseRequest(BaseModel):
    name: str = Field(min_length=1)


class RelocateWarehouseRequest(BaseModel):
    address_line: str = Field(min_length=1)


class SetWarehouseActiveRequest(BaseModel):
    is_active: bool


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


class PriceListProposalResponse(BaseModel):
    """One row of the OMC rate-review queue (AI Operational Intelligence,
    Horizon 1 Stage 3) — a heuristic-fetched proposal awaiting staff
    accept/reject, not yet a price. `source_url` is where the number came
    from, so a reviewer can verify it before accepting."""

    id: str
    cylinder_type_id: str
    customer_type: str
    branch_id: str | None
    proposed_price: Decimal
    effective_from: datetime
    source_url: str
    status: str
    fetched_at: datetime
    reviewed_by: str | None
    reviewed_at: datetime | None


class PriceListProposalListResponse(BaseModel):
    items: list[PriceListProposalResponse]


class ReviewPriceListProposalRequest(BaseModel):
    action: Literal["accept", "reject"]


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


class FeatureFlagSummaryResponse(BaseModel):
    """Key + description only — the tenant-facing flag picker. Deliberately
    excludes `rollout_percentage`/`starts_at`/`ends_at`: those are platform
    rollout mechanics, not something a tenant admin needs or should see when
    choosing a flag to override for their own tenant."""

    key: str
    description: str


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
