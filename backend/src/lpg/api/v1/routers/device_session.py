"""A phone asking the server about itself (ADR-071).

`GET /devices/me` is the one authenticated call a phone that is waiting for
approval, or has just been blocked, can still make — it is how the "Waiting
for approval" screen finds out it was approved, and how a running app learns
it must sign out. It needs a valid session opened on the calling phone, but
does not require the phone to be approved.
"""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import status as http_status

from lpg.api.v1.dependencies.device import (
    get_device_access_gate,
    get_device_namer,
    install_id_from,
)
from lpg.api.v1.dependencies.tenant import get_tenant_context_any_device_state
from lpg.api.v1.schemas.devices import MyDeviceResponse, NameMyDeviceRequest
from lpg.application.common.ports import TenantContext
from lpg.application.identity.ports import AuthenticatedPrincipal
from lpg.application.license.device_access import DRIVER_ROLE, DeviceAccessGate
from lpg.application.license.manage_devices import NameOwnDeviceCommand
from lpg.application.license.ports import DeviceNamer
from lpg.domain.license.linked_device import DeviceStatus

router = APIRouter(prefix="/devices", tags=["Device session"])


def get_phone_principal(
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context_any_device_state)],
) -> AuthenticatedPrincipal:
    """The caller, whatever state their phone is in."""
    return cast("AuthenticatedPrincipal", tenant_context)


@router.get(
    "/me",
    response_model=MyDeviceResponse,
    summary="This phone's approval state and whether the agency lets it in",
)
async def get_my_device(
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_phone_principal)],
    gate: Annotated[DeviceAccessGate, Depends(get_device_access_gate)],
) -> MyDeviceResponse:
    mode = await gate.mode(principal.tenant_id)
    access = await gate.check(
        tenant_id=principal.tenant_id,
        role=principal.role,
        device_id=getattr(principal, "device_id", None),
        install_id=install_id_from(request),
        enforce_status=False,
    )
    status = access.status if access else None
    controlled = access is not None or principal.role == DRIVER_ROLE
    allowed = (not mode.enforces) or (not controlled) or status is DeviceStatus.APPROVED
    return MyDeviceResponse(
        control=mode.value,
        status=status.value if status else None,
        display_name=access.display_name if access else None,
        allowed=allowed,
        needs_name=access is not None and not access.name_confirmed,
    )


@router.put(
    "/me/name",
    response_model=MyDeviceResponse,
    summary="Name this phone (asked once, for a phone the agency has not seen)",
)
async def name_my_device(
    body: NameMyDeviceRequest,
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_phone_principal)],
    gate: Annotated[DeviceAccessGate, Depends(get_device_access_gate)],
    namer: Annotated[DeviceNamer, Depends(get_device_namer)],
) -> MyDeviceResponse:
    device_id = getattr(principal, "device_id", None)
    if device_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT, detail="This session is not tied to a phone."
        )
    # Same identity check as every request: only the phone itself may name it.
    await gate.check(
        tenant_id=principal.tenant_id,
        role=principal.role,
        device_id=device_id,
        install_id=install_id_from(request),
        enforce_status=False,
    )
    await namer.name(
        NameOwnDeviceCommand(
            tenant_id=principal.tenant_id,
            device_id=device_id,
            name=body.name,
            user_id=principal.user_id,
        )
    )
    await gate.forget(principal.tenant_id, device_id)
    return await get_my_device(request, principal, gate)
