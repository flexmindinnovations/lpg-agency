"""A phone asking the server about itself (ADR-071).

`GET /devices/me` is the one authenticated call a phone that is waiting for
approval, or has just been blocked, can still make — it is how the "Waiting
for approval" screen finds out it was approved, and how a running app learns
it must sign out. It needs a valid session opened on the calling phone, but
does not require the phone to be approved.
"""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request

from lpg.api.v1.dependencies.device import get_device_access_gate, install_id_from
from lpg.api.v1.dependencies.tenant import get_tenant_context_any_device_state
from lpg.api.v1.schemas.devices import MyDeviceResponse
from lpg.application.common.ports import TenantContext
from lpg.application.identity.ports import AuthenticatedPrincipal
from lpg.application.license.device_access import DRIVER_ROLE, DeviceAccessGate
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
    )
