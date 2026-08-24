"""Request/response schemas for `/admin/license/*` and `/license/status`."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class IssueLicenseRequest(BaseModel):
    tenant_id: str
    plan_tier: str = Field(min_length=1)
    validity_days: int = Field(default=365, gt=0)
    device_caps: dict[str, int | None] | None = None


class IssuedLicenseResponse(BaseModel):
    """The **only** response that ever carries `plaintext_key` — shown once,
    at issuance, and never retrievable again."""

    tenant_id: str
    plaintext_key: str
    key_prefix: str
    plan_tier: str
    issued_at: datetime


class LicenseResponse(BaseModel):
    tenant_id: str
    #: Populated only by `/platform/license` (`routers/platform.py`'s own
    #: `_license_response()`) — the cross-tenant list view a super_admin
    #: needs to identify *whose* license each row is, since `tenant_id`
    #: alone isn't human-readable. Left `None` for the tenant self-service
    #: `/admin/license` response (`routers/admin.py`) — a tenant already
    #: knows who it is.
    tenant_name: str | None = None
    status: str
    plan_tier: str
    key_prefix: str
    device_caps: dict[str, int | None]
    issued_at: datetime
    activated_at: datetime | None
    expires_at: datetime | None
    grace_ends_at: datetime | None
    revoked_at: datetime | None


class ActivateLicenseRequest(BaseModel):
    key: str = Field(min_length=1)


class LicenseStatusResponse(BaseModel):
    status: str
    plan_tier: str | None
    key_prefix: str | None
    activated_at: datetime | None
    expires_at: datetime | None
    grace_ends_at: datetime | None


class SetLicensePlanTierRequest(BaseModel):
    plan_tier: str = Field(min_length=1)


class SetLicenseDeviceCapRequest(BaseModel):
    max_devices: int | None = Field(default=None, ge=0)


class SetLicenseFeatureOverrideRequest(BaseModel):
    granted: bool


class LinkedDeviceResponse(BaseModel):
    id: str
    app_type: str
    device_identifier: str
    display_name: str
    registered_at: datetime
    last_seen_at: datetime
    revoked_at: datetime | None
    is_active: bool


class RegisterDeviceRequest(BaseModel):
    """No caller in this repository yet — the contract for a future
    mobile-facing endpoint."""

    app_type: str = Field(min_length=1)
    device_identifier: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
