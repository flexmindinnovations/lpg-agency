"""Support contacts for the apps' Support screens.

- `GET /support/contacts` — the gas-leak emergency helpline and the agency's
  support phone. Any signed-in user of the tenant may read them; they are
  the numbers printed on every cylinder delivery slip anyway.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from lpg.api.v1.dependencies.admin import get_tenant_configuration_repository
from lpg.api.v1.dependencies.identity import get_current_principal
from lpg.application.identity.ports import AuthenticatedPrincipal
from lpg.application.tenant.ports import TenantConfigurationRepository
from lpg.application.tenant.tenant_configuration import (
    GetSupportContactsQuery,
    GetSupportContactsUseCase,
)
from lpg.config.settings import Settings, get_settings

router = APIRouter(prefix="/support", tags=["Support"])


class SupportContactsResponse(BaseModel):
    emergency_helpline: str
    agency_phone: str | None


@router.get(
    "/contacts",
    response_model=SupportContactsResponse,
    summary="The emergency helpline and the agency's support phone",
)
async def get_support_contacts(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[
        TenantConfigurationRepository, Depends(get_tenant_configuration_repository)
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SupportContactsResponse:
    contacts = await GetSupportContactsUseCase(
        repository, default_emergency_helpline=settings.emergency_helpline_number
    ).execute(GetSupportContactsQuery(tenant_id=principal.tenant_id))
    return SupportContactsResponse(
        emergency_helpline=contacts.emergency_helpline, agency_phone=contacts.agency_phone
    )
