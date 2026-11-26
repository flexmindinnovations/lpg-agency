"""Platform-side correction of an agency's own details - `super_admin` only,
live-checked at the router like the lifecycle actions in
`manage_lifecycle.py`. Distinct from `rename_tenant.py`, which is the
tenant-scoped rename an agency performs on itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command
from lpg.application.common.errors import NotFoundError

if TYPE_CHECKING:
    import uuid

    from lpg.application.common.ports import UnitOfWork
    from lpg.application.tenant.ports import TenantRepository
    from lpg.domain.tenant.tenant import Tenant


@dataclass(frozen=True, slots=True)
class UpdateAgencyDetailsCommand(Command):
    tenant_id: uuid.UUID
    name: str
    primary_contact_email: str


class UpdateAgencyDetailsUseCase:
    def __init__(self, repository: TenantRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: UpdateAgencyDetailsCommand) -> Tenant:
        tenant = await self._repository.get(command.tenant_id)
        if tenant is None:
            msg = f"No agency '{command.tenant_id}'."
            raise NotFoundError(msg, tenant_id=str(command.tenant_id))

        tenant.update_details(
            name=command.name, primary_contact_email=command.primary_contact_email
        )

        await self._repository.save(tenant)
        await self._unit_of_work.commit()
        return tenant
