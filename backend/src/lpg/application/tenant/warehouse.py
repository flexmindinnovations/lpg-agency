"""`CreateWarehouseUseCase` / `RenameWarehouseUseCase` / `RelocateWarehouseUseCase`.

Same plain tenant-scoped RLS-backed CRUD pattern as `branch.py` — see that
module's docstring.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command
from lpg.application.common.errors import NotFoundError
from lpg.domain.tenant.warehouse import Warehouse

if TYPE_CHECKING:
    from lpg.application.common.ports import UnitOfWork
    from lpg.application.tenant.ports import WarehouseRepository


@dataclass(frozen=True, slots=True)
class CreateWarehouseCommand(Command):
    tenant_id: uuid.UUID
    branch_id: uuid.UUID
    name: str
    address_line: str


class CreateWarehouseUseCase:
    def __init__(self, repository: WarehouseRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: CreateWarehouseCommand) -> Warehouse:
        warehouse = Warehouse(
            uuid.uuid4(),
            command.tenant_id,
            command.branch_id,
            command.name,
            command.address_line,
        )
        await self._repository.add(warehouse)
        await self._unit_of_work.commit()
        return warehouse


@dataclass(frozen=True, slots=True)
class RenameWarehouseCommand(Command):
    warehouse_id: uuid.UUID
    new_name: str


class RenameWarehouseUseCase:
    def __init__(self, repository: WarehouseRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: RenameWarehouseCommand) -> None:
        warehouse = await self._repository.get(command.warehouse_id)
        if warehouse is None:
            msg = f"No warehouse visible with id {command.warehouse_id}."
            raise NotFoundError(msg, warehouse_id=str(command.warehouse_id))

        warehouse.rename(command.new_name)

        await self._repository.save(warehouse)
        await self._unit_of_work.commit()


@dataclass(frozen=True, slots=True)
class RelocateWarehouseCommand(Command):
    warehouse_id: uuid.UUID
    new_address_line: str


class RelocateWarehouseUseCase:
    def __init__(self, repository: WarehouseRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: RelocateWarehouseCommand) -> None:
        warehouse = await self._repository.get(command.warehouse_id)
        if warehouse is None:
            msg = f"No warehouse visible with id {command.warehouse_id}."
            raise NotFoundError(msg, warehouse_id=str(command.warehouse_id))

        warehouse.relocate(command.new_address_line)

        await self._repository.save(warehouse)
        await self._unit_of_work.commit()


@dataclass(frozen=True, slots=True)
class ListWarehousesQuery:
    tenant_id: uuid.UUID


class ListWarehousesUseCase:
    def __init__(self, repository: WarehouseRepository) -> None:
        self._repository = repository

    async def execute(self, query: ListWarehousesQuery) -> list[Warehouse]:
        return list(await self._repository.list_for_tenant(query.tenant_id))
