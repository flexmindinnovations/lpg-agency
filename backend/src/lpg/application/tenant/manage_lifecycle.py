"""Platform-side tenant (agency) lifecycle management — `super_admin` only,
all live-checked (`require_live_platform_permission("tenant:manage_platform")`),
the same sensitivity tier `license:manage_platform` uses.

Wires up `Tenant.activate()`/`.suspend()`/`.reactivate()`/`.close()`
(`domain/tenant/tenant.py`) for the first time — those domain methods have
existed since the table's own status columns were reconciled onto it
(`b1c4a9e7d2f3`), fully implemented, but never called by anything until
this file.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command
from lpg.application.common.errors import NotFoundError

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from lpg.application.common.ports import UnitOfWork
    from lpg.application.tenant.ports import TenantRepository
    from lpg.application.tenant.status import TenantStatusChecker
    from lpg.domain.tenant.tenant import Tenant


@dataclass(frozen=True, slots=True)
class SuspendTenantCommand(Command):
    tenant_id: uuid.UUID


class SuspendTenantUseCase:
    def __init__(
        self,
        repository: TenantRepository,
        status_checker: TenantStatusChecker,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._status_checker = status_checker
        self._unit_of_work = unit_of_work

    async def execute(self, command: SuspendTenantCommand) -> None:
        tenant = await self._repository.get(command.tenant_id)
        if tenant is None:
            msg = f"No tenant visible with id {command.tenant_id}."
            raise NotFoundError(msg, tenant_id=str(command.tenant_id))

        tenant.suspend()

        await self._repository.save(tenant)
        await self._unit_of_work.commit()
        await self._status_checker.invalidate(command.tenant_id)


@dataclass(frozen=True, slots=True)
class ReactivateTenantCommand(Command):
    tenant_id: uuid.UUID


class ReactivateTenantUseCase:
    def __init__(
        self,
        repository: TenantRepository,
        status_checker: TenantStatusChecker,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._status_checker = status_checker
        self._unit_of_work = unit_of_work

    async def execute(self, command: ReactivateTenantCommand) -> None:
        tenant = await self._repository.get(command.tenant_id)
        if tenant is None:
            msg = f"No tenant visible with id {command.tenant_id}."
            raise NotFoundError(msg, tenant_id=str(command.tenant_id))

        tenant.reactivate()

        await self._repository.save(tenant)
        await self._unit_of_work.commit()
        await self._status_checker.invalidate(command.tenant_id)


@dataclass(frozen=True, slots=True)
class CloseTenantCommand(Command):
    tenant_id: uuid.UUID


class CloseTenantUseCase:
    """Terminal — `Tenant.close()` never allows a way back
    (`domain/tenant/tenant.py`'s own docstring: "never reopened")."""

    def __init__(
        self,
        repository: TenantRepository,
        status_checker: TenantStatusChecker,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._status_checker = status_checker
        self._unit_of_work = unit_of_work

    async def execute(self, command: CloseTenantCommand) -> None:
        tenant = await self._repository.get(command.tenant_id)
        if tenant is None:
            msg = f"No tenant visible with id {command.tenant_id}."
            raise NotFoundError(msg, tenant_id=str(command.tenant_id))

        tenant.close()

        await self._repository.save(tenant)
        await self._unit_of_work.commit()
        await self._status_checker.invalidate(command.tenant_id)


@dataclass(frozen=True, slots=True)
class ListTenantsQuery:
    pass


class ListTenantsUseCase:
    """Backs the Agency Management page — the one genuinely cross-tenant
    read in this module. `repository.list_all()` only resolves at all
    through the `/platform/*` dependency chain (an unscoped session reading
    via `tenant.tenant_list_all()`, migration `fdd3afde337c`); called
    through the ordinary tenant-scoped path it would see at most one row,
    per `tenant.tenant`'s own RLS policy.
    """

    def __init__(self, repository: TenantRepository) -> None:
        self._repository = repository

    async def execute(self, query: ListTenantsQuery) -> Sequence[Tenant]:
        del query
        return await self._repository.list_all()
