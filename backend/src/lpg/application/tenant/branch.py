"""`CreateBranchUseCase` / `RenameBranchUseCase` / `SetBranchRegionUseCase`.

Plain, normal tenant-scoped RLS-backed CRUD — unlike Phase 6's Identity use
cases, there is no pre-authentication chicken-and-egg problem here: every
call runs after the JWT has already resolved a `TenantContext`, so the
ordinary `TenantRepository`-style pattern (repository → `UnitOfWork`)
applies directly, no `SECURITY DEFINER` function needed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command
from lpg.application.common.errors import NotFoundError
from lpg.domain.tenant.branch import Branch

if TYPE_CHECKING:
    from lpg.application.common.ports import UnitOfWork
    from lpg.application.tenant.ports import BranchRepository


@dataclass(frozen=True, slots=True)
class CreateBranchCommand(Command):
    tenant_id: uuid.UUID
    name: str
    region: str | None = None


class CreateBranchUseCase:
    def __init__(self, repository: BranchRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: CreateBranchCommand) -> Branch:
        branch = Branch(uuid.uuid4(), command.tenant_id, command.name, command.region)
        await self._repository.add(branch)
        await self._unit_of_work.commit()
        return branch


@dataclass(frozen=True, slots=True)
class RenameBranchCommand(Command):
    branch_id: uuid.UUID
    new_name: str


class RenameBranchUseCase:
    def __init__(self, repository: BranchRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: RenameBranchCommand) -> None:
        branch = await self._repository.get(command.branch_id)
        if branch is None:
            msg = f"No branch visible with id {command.branch_id}."
            raise NotFoundError(msg, branch_id=str(command.branch_id))

        branch.rename(command.new_name)

        await self._repository.save(branch)
        await self._unit_of_work.commit()


@dataclass(frozen=True, slots=True)
class SetBranchRegionCommand(Command):
    branch_id: uuid.UUID
    region: str | None


class SetBranchRegionUseCase:
    def __init__(self, repository: BranchRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: SetBranchRegionCommand) -> None:
        branch = await self._repository.get(command.branch_id)
        if branch is None:
            msg = f"No branch visible with id {command.branch_id}."
            raise NotFoundError(msg, branch_id=str(command.branch_id))

        branch.set_region(command.region)

        await self._repository.save(branch)
        await self._unit_of_work.commit()


@dataclass(frozen=True, slots=True)
class ListBranchesQuery:
    tenant_id: uuid.UUID


class ListBranchesUseCase:
    def __init__(self, repository: BranchRepository) -> None:
        self._repository = repository

    async def execute(self, query: ListBranchesQuery) -> list[Branch]:
        return list(await self._repository.list_for_tenant(query.tenant_id))
