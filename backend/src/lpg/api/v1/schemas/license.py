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
    """One phone running the Driver or Admin app. The install ID and the
    hardware ID are never returned (they are stored hashed); `device_ref` and
    `phone_ref` are short fingerprints an admin can compare by eye."""

    id: str
    app_type: str
    display_name: str
    status: str = Field(description="pending, approved, blocked or removed.")
    manufacturer: str | None
    model: str | None
    os_version: str | None
    app_version: str | None
    platform: str | None
    device_ref: str
    phone_ref: str | None
    asset_note: str | None = Field(description="IMEI or serial the admin typed; a note only.")
    last_user_id: str | None
    last_user_name: str | None
    registered_at: datetime
    last_seen_at: datetime
    status_changed_at: datetime
    removed_at: datetime | None


class UpdateLinkedDeviceRequest(BaseModel):
    """Only the fields that are sent change. An empty `asset_note` clears it."""

    display_name: str | None = Field(default=None, min_length=1, max_length=60)
    asset_note: str | None = Field(default=None, max_length=64)


class PendingDeviceCountResponse(BaseModel):
    count: int


class DeviceHistoryEntryResponse(BaseModel):
    id: str
    action: str = Field(description="registered, approved, blocked, unblocked, removed or updated.")
    performed_at: datetime
    actor_name: str | None
    from_status: str | None
    to_status: str | None
    display_name: str | None
