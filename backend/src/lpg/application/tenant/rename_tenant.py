"""`RenameTenantUseCase` — Phase 2's one illustrative Command → Application
Service → Repository → UoW → domain event example.

Traces exactly the flow `03-backend-architecture.md` §2 illustrates:

    RenameTenantCommand
      → RenameTenantUseCase.execute(command)
        → TenantRepository.get(tenant_id)   # aggregate, RLS-scoped
        → tenant.rename(new_name)           # domain behaviour, invariant enforced here
        → TenantRepository.save(tenant)
        → uow.commit()                      # transaction + (future) audit + event dispatch

Not a real business use case — see `lpg.domain.tenant.tenant`'s module
docstring for why "renaming your own tenant" is the deliberately narrow
scope this proof uses.
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


@dataclass(frozen=True, slots=True)
class RenameTenantCommand(Command):
    tenant_id: uuid.UUID
    new_name: str


class RenameTenantUseCase:
    """Application-layer use case — plain constructor injection, no DI
    container, no framework dependency (`03-backend-architecture.md` §5)."""

    def __init__(self, repository: TenantRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: RenameTenantCommand) -> None:
        tenant = await self._repository.get(command.tenant_id)
        if tenant is None:
            msg = f"No tenant visible with id {command.tenant_id}."
            raise NotFoundError(msg, tenant_id=str(command.tenant_id))

        tenant.rename(command.new_name)

        await self._repository.save(tenant)
        await self._unit_of_work.commit()
