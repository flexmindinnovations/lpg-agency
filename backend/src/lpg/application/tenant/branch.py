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
from lpg.application.common.errors import ConflictError, NotFoundError
from lpg.domain.tenant.branch import Branch

if TYPE_CHECKING:
    from lpg.application.common.ports import UnitOfWork
    from lpg.application.tenant.ports import BranchRepository


@dataclass(frozen=True, slots=True)
class CreateBranchCommand(Command):
    tenant_id: uuid.UUID
    name: str
    region: str | None = None


async def _refuse_duplicate_name(
    repository: BranchRepository,
    tenant_id: uuid.UUID,
    name: str,
    *,
    except_id: uuid.UUID | None = None,
) -> None:
    """Branch names are unique per agency, ignoring case and outer spaces
    (DA-19: two "QA Branch" rows were indistinguishable in every picker).
    Inactive branches count too - reactivating one must not create a clash."""
    wanted = name.strip().casefold()
    for existing in await repository.list_for_tenant(tenant_id):
        if existing.id != except_id and existing.name.strip().casefold() == wanted:
            msg = f"A branch named '{existing.name}' already exists."
            raise ConflictError(msg, branch_id=str(existing.id))


class CreateBranchUseCase:
    def __init__(self, repository: BranchRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: CreateBranchCommand) -> Branch:
        branch = Branch.create(uuid.uuid4(), command.tenant_id, command.name, command.region)
        await _refuse_duplicate_name(self._repository, command.tenant_id, branch.name)
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

        await _refuse_duplicate_name(
            self._repository, branch.tenant_id, command.new_name, except_id=branch.id
        )
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
class SetBranchActiveCommand(Command):
    branch_id: uuid.UUID
    is_active: bool


class SetBranchActiveUseCase:
    def __init__(self, repository: BranchRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: SetBranchActiveCommand) -> None:
        branch = await self._repository.get(command.branch_id)
        if branch is None:
            msg = f"No branch visible with id {command.branch_id}."
            raise NotFoundError(msg, branch_id=str(command.branch_id))

        if command.is_active:
            branch.activate()
        else:
            branch.deactivate()

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
