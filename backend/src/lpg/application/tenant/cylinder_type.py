"""`CreateCylinderTypeUseCase` / `RenameCylinderTypeUseCase` /
`AdjustCylinderTypeWeightUseCase` / `SetCylinderTypeActiveUseCase`.

Same plain tenant-scoped RLS-backed CRUD pattern as `branch.py`/
`warehouse.py`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command
from lpg.application.common.errors import NotFoundError
from lpg.domain.tenant.cylinder_type import CylinderType

if TYPE_CHECKING:
    from decimal import Decimal

    from lpg.application.common.ports import UnitOfWork
    from lpg.application.tenant.ports import CylinderTypeRepository


@dataclass(frozen=True, slots=True)
class CreateCylinderTypeCommand(Command):
    tenant_id: uuid.UUID
    name: str
    weight_kg: Decimal


class CreateCylinderTypeUseCase:
    def __init__(self, repository: CylinderTypeRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: CreateCylinderTypeCommand) -> CylinderType:
        cylinder_type = CylinderType(
            uuid.uuid4(), command.tenant_id, command.name, command.weight_kg
        )
        await self._repository.add(cylinder_type)
        await self._unit_of_work.commit()
        return cylinder_type


@dataclass(frozen=True, slots=True)
class RenameCylinderTypeCommand(Command):
    cylinder_type_id: uuid.UUID
    new_name: str


class RenameCylinderTypeUseCase:
    def __init__(self, repository: CylinderTypeRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: RenameCylinderTypeCommand) -> None:
        cylinder_type = await self._repository.get(command.cylinder_type_id)
        if cylinder_type is None:
            msg = f"No cylinder type visible with id {command.cylinder_type_id}."
            raise NotFoundError(msg, cylinder_type_id=str(command.cylinder_type_id))

        cylinder_type.rename(command.new_name)

        await self._repository.save(cylinder_type)
        await self._unit_of_work.commit()


@dataclass(frozen=True, slots=True)
class AdjustCylinderTypeWeightCommand(Command):
    cylinder_type_id: uuid.UUID
    new_weight_kg: Decimal


class AdjustCylinderTypeWeightUseCase:
    def __init__(self, repository: CylinderTypeRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: AdjustCylinderTypeWeightCommand) -> None:
        cylinder_type = await self._repository.get(command.cylinder_type_id)
        if cylinder_type is None:
            msg = f"No cylinder type visible with id {command.cylinder_type_id}."
            raise NotFoundError(msg, cylinder_type_id=str(command.cylinder_type_id))

        cylinder_type.adjust_weight(command.new_weight_kg)

        await self._repository.save(cylinder_type)
        await self._unit_of_work.commit()


@dataclass(frozen=True, slots=True)
class SetCylinderTypeActiveCommand(Command):
    cylinder_type_id: uuid.UUID
    is_active: bool


class SetCylinderTypeActiveUseCase:
    def __init__(self, repository: CylinderTypeRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: SetCylinderTypeActiveCommand) -> None:
        cylinder_type = await self._repository.get(command.cylinder_type_id)
        if cylinder_type is None:
            msg = f"No cylinder type visible with id {command.cylinder_type_id}."
            raise NotFoundError(msg, cylinder_type_id=str(command.cylinder_type_id))

        if command.is_active:
            cylinder_type.activate()
        else:
            cylinder_type.deactivate()

        await self._repository.save(cylinder_type)
        await self._unit_of_work.commit()


@dataclass(frozen=True, slots=True)
class ListCylinderTypesQuery:
    tenant_id: uuid.UUID


class ListCylinderTypesUseCase:
    def __init__(self, repository: CylinderTypeRepository) -> None:
        self._repository = repository

    async def execute(self, query: ListCylinderTypesQuery) -> list[CylinderType]:
        return list(await self._repository.list_for_tenant(query.tenant_id))
