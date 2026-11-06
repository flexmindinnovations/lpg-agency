"""Linked devices — the agency admin's view of the phones running the Driver
and Admin apps (ADR-071). Every route needs `license:manage_tenant` (agency
admin) and is confined to the caller's own tenant.

Not to be confused with `POST /notifications/devices`, which stores a push
token against a user and says nothing about who owns the phone.

**Every type used inside `Annotated[X, Depends(...)]` below is a real import,
never `TYPE_CHECKING`-guarded** — see `routers/auth.py`'s module docstring.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from lpg.api.v1.dependencies.admin import get_audit_log_repository, get_audit_trail
from lpg.api.v1.dependencies.identity import require_permission
from lpg.api.v1.dependencies.license import get_license_repository, get_linked_device_repository
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.api.v1.schemas.license import (
    DeviceHistoryEntryResponse,
    LinkedDeviceResponse,
    PendingDeviceCountResponse,
    UpdateLinkedDeviceRequest,
)
from lpg.application.audit.ports import AuditLogEntry, AuditLogRepository, AuditTrail
from lpg.application.common.ports import UnitOfWork
from lpg.application.identity.ports import AuthenticatedPrincipal
from lpg.application.license.manage_devices import (
    ChangeDeviceStatusCommand,
    ChangeDeviceStatusUseCase,
    CountPendingDevicesQuery,
    CountPendingDevicesUseCase,
    DeviceAction,
    GetDeviceHistoryQuery,
    GetDeviceHistoryUseCase,
    ListLinkedDevicesQuery,
    ListLinkedDevicesUseCase,
    UpdateDeviceDetailsCommand,
    UpdateDeviceDetailsUseCase,
)
from lpg.application.license.ports import LicenseRepository, LinkedDeviceRepository
from lpg.domain.license.linked_device import DeviceStatus, LinkedDevice

router = APIRouter(prefix="/admin/license/devices", tags=["Linked devices"])

_ManageDevices = Annotated[
    AuthenticatedPrincipal, Depends(require_permission("license:manage_tenant"))
]

_REF_LENGTH = 8


def _short_ref(fingerprint: str | None) -> str | None:
    """First characters of a stored hash — enough to tell phones apart."""
    return fingerprint[:_REF_LENGTH].upper() if fingerprint else None


def _device_response(device: LinkedDevice) -> LinkedDeviceResponse:
    details = device.details
    return LinkedDeviceResponse(
        id=str(device.id),
        app_type=device.app_type,
        display_name=device.display_name,
        status=device.status.value,
        manufacturer=details.manufacturer,
        model=details.model,
        os_version=details.os_version,
        app_version=details.app_version,
        platform=details.platform,
        device_ref=_short_ref(device.device_identifier) or "",
        phone_ref=_short_ref(device.hardware_ref),
        asset_note=device.asset_note,
        last_user_id=str(device.last_user_id) if device.last_user_id else None,
        last_user_name=device.last_user_name,
        registered_at=device.registered_at,
        last_seen_at=device.last_seen_at,
        status_changed_at=device.status_changed_at,
        removed_at=device.revoked_at,
    )


def _history_response(entry: AuditLogEntry) -> DeviceHistoryEntryResponse:
    before = entry.before_state or {}
    after = entry.after_state or {}
    return DeviceHistoryEntryResponse(
        id=str(entry.id),
        action=entry.action.removeprefix("device."),
        performed_at=entry.performed_at,
        actor_name=entry.actor_display_name,
        from_status=before.get("status"),
        to_status=after.get("status"),
        display_name=after.get("display_name") or entry.entity_display_name,
    )


@router.get("", response_model=list[LinkedDeviceResponse], summary="List this agency's phones")
async def list_linked_devices(
    principal: _ManageDevices,
    repository: Annotated[LinkedDeviceRepository, Depends(get_linked_device_repository)],
    app_type: Annotated[str | None, Query(description="driver_app or admin_app.")] = None,
    status: Annotated[
        DeviceStatus | None,
        Query(description="Leave out to list every phone still in use (not removed)."),
    ] = None,
) -> list[LinkedDeviceResponse]:
    use_case = ListLinkedDevicesUseCase(repository)
    devices = await use_case.execute(
        ListLinkedDevicesQuery(tenant_id=principal.tenant_id, app_type=app_type, status=status)
    )
    return [_device_response(device) for device in devices]


@router.get(
    "/pending-count",
    response_model=PendingDeviceCountResponse,
    summary="How many phones are waiting for approval",
)
async def count_pending_devices(
    principal: _ManageDevices,
    repository: Annotated[LinkedDeviceRepository, Depends(get_linked_device_repository)],
) -> PendingDeviceCountResponse:
    use_case = CountPendingDevicesUseCase(repository)
    count = await use_case.execute(CountPendingDevicesQuery(tenant_id=principal.tenant_id))
    return PendingDeviceCountResponse(count=count)


@router.get(
    "/{device_id}/history",
    response_model=list[DeviceHistoryEntryResponse],
    summary="Who did what to this phone",
)
async def get_device_history(
    device_id: uuid.UUID,
    principal: _ManageDevices,
    repository: Annotated[LinkedDeviceRepository, Depends(get_linked_device_repository)],
    audit_log: Annotated[AuditLogRepository, Depends(get_audit_log_repository)],
) -> list[DeviceHistoryEntryResponse]:
    use_case = GetDeviceHistoryUseCase(repository, audit_log)
    entries = await use_case.execute(
        GetDeviceHistoryQuery(tenant_id=principal.tenant_id, device_id=device_id)
    )
    return [_history_response(entry) for entry in entries]


def get_change_device_status_use_case(
    license_repository: Annotated[LicenseRepository, Depends(get_license_repository)],
    repository: Annotated[LinkedDeviceRepository, Depends(get_linked_device_repository)],
    audit: Annotated[AuditTrail, Depends(get_audit_trail)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> ChangeDeviceStatusUseCase:
    return ChangeDeviceStatusUseCase(license_repository, repository, audit, unit_of_work)


_StatusChange = Annotated[ChangeDeviceStatusUseCase, Depends(get_change_device_status_use_case)]


async def _change_status(
    use_case: ChangeDeviceStatusUseCase,
    action: DeviceAction,
    device_id: uuid.UUID,
    principal: AuthenticatedPrincipal,
) -> LinkedDeviceResponse:
    device = await use_case.execute(
        ChangeDeviceStatusCommand(
            tenant_id=principal.tenant_id,
            device_id=device_id,
            actor_id=principal.user_id,
            action=action,
        )
    )
    return _device_response(device)


@router.post(
    "/{device_id}/approve", response_model=LinkedDeviceResponse, summary="Approve a waiting phone"
)
async def approve_device(
    device_id: uuid.UUID, principal: _ManageDevices, use_case: _StatusChange
) -> LinkedDeviceResponse:
    return await _change_status(use_case, DeviceAction.APPROVE, device_id, principal)


@router.post("/{device_id}/block", response_model=LinkedDeviceResponse, summary="Block a phone")
async def block_device(
    device_id: uuid.UUID, principal: _ManageDevices, use_case: _StatusChange
) -> LinkedDeviceResponse:
    return await _change_status(use_case, DeviceAction.BLOCK, device_id, principal)


@router.post(
    "/{device_id}/unblock", response_model=LinkedDeviceResponse, summary="Unblock a blocked phone"
)
async def unblock_device(
    device_id: uuid.UUID, principal: _ManageDevices, use_case: _StatusChange
) -> LinkedDeviceResponse:
    return await _change_status(use_case, DeviceAction.UNBLOCK, device_id, principal)


@router.post(
    "/{device_id}/remove",
    response_model=LinkedDeviceResponse,
    summary="Remove a phone from the list",
)
async def remove_device(
    device_id: uuid.UUID, principal: _ManageDevices, use_case: _StatusChange
) -> LinkedDeviceResponse:
    return await _change_status(use_case, DeviceAction.REMOVE, device_id, principal)


@router.patch(
    "/{device_id}",
    response_model=LinkedDeviceResponse,
    summary="Rename a phone or set its IMEI / serial note",
)
async def update_device(
    device_id: uuid.UUID,
    body: UpdateLinkedDeviceRequest,
    principal: _ManageDevices,
    repository: Annotated[LinkedDeviceRepository, Depends(get_linked_device_repository)],
    audit: Annotated[AuditTrail, Depends(get_audit_trail)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> LinkedDeviceResponse:
    use_case = UpdateDeviceDetailsUseCase(repository, audit, unit_of_work)
    device = await use_case.execute(
        UpdateDeviceDetailsCommand(
            tenant_id=principal.tenant_id,
            device_id=device_id,
            actor_id=principal.user_id,
            display_name=body.display_name,
            asset_note=body.asset_note,
            change_asset_note="asset_note" in body.model_fields_set,
        )
    )
    return _device_response(device)
