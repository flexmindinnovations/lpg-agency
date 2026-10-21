"""`UpdateAgencyBusinessProfileUseCase` — the agency's GST supplier details
(legal name, address, state, GSTIN) that every tax invoice prints (DA-13).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command
from lpg.application.common.errors import NotFoundError
from lpg.domain.tenant.tenant import AgencyBusinessProfile

if TYPE_CHECKING:
    import uuid

    from lpg.application.common.ports import UnitOfWork
    from lpg.application.tenant.ports import TenantRepository
    from lpg.domain.tenant.tenant import Tenant


@dataclass(frozen=True, slots=True)
class UpdateAgencyBusinessProfileCommand(Command):
    tenant_id: uuid.UUID
    legal_name: str
    address_line_1: str
    city: str
    state_code: str
    pincode: str
    gstin: str | None = None
    address_line_2: str | None = None
    phone: str | None = None


class UpdateAgencyBusinessProfileUseCase:
    def __init__(self, repository: TenantRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: UpdateAgencyBusinessProfileCommand) -> Tenant:
        tenant = await self._repository.get(command.tenant_id)
        if tenant is None:
            msg = f"No tenant visible with id {command.tenant_id}."
            raise NotFoundError(msg, tenant_id=str(command.tenant_id))

        tenant.update_business_profile(
            AgencyBusinessProfile.create(
                legal_name=command.legal_name,
                address_line_1=command.address_line_1,
                address_line_2=command.address_line_2,
                city=command.city,
                state_code=command.state_code,
                pincode=command.pincode,
                gstin=command.gstin,
                phone=command.phone,
            )
        )

        await self._repository.save(tenant)
        await self._unit_of_work.commit()
        return tenant
