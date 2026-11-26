"""Create, change, delete, activate and GST-classify cylinder types.

Same plain tenant-scoped RLS-backed CRUD pattern as `branch.py`/
`warehouse.py`. Sizes come from the standard list only (ADR-079).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command
from lpg.application.common.errors import ConflictError, NotFoundError, ValidationError
from lpg.domain.tenant.cylinder_catalog import CYLINDER_SIZES, size_by_code
from lpg.domain.tenant.cylinder_type import CylinderType

if TYPE_CHECKING:
    from collections.abc import Sequence
    from decimal import Decimal

    from lpg.application.common.ports import UnitOfWork
    from lpg.application.tenant.ports import CylinderTypeRepository
    from lpg.domain.tenant.cylinder_catalog import CylinderSize


def _require_size(size_code: str) -> CylinderSize:
    size = size_by_code(size_code)
    if size is None:
        msg = "Choose a cylinder size from the standard list."
        raise ValidationError(msg, size_code=size_code)
    return size


async def _require_cylinder_type(
    repository: CylinderTypeRepository, cylinder_type_id: uuid.UUID
) -> CylinderType:
    cylinder_type = await repository.get(cylinder_type_id)
    if cylinder_type is None:
        msg = f"No cylinder type visible with id {cylinder_type_id}."
        raise NotFoundError(msg, cylinder_type_id=str(cylinder_type_id))
    return cylinder_type


async def _require_size_not_added(
    repository: CylinderTypeRepository,
    tenant_id: uuid.UUID,
    size: CylinderSize,
    *,
    ignoring: uuid.UUID | None = None,
) -> None:
    for existing in await repository.list_for_tenant(tenant_id):
        if existing.id != ignoring and existing.name.casefold() == size.name.casefold():
            msg = f"{size.name} is already in your cylinder types."
            raise ConflictError(msg, size_code=size.code)


def _in_words(items: Sequence[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


@dataclass(frozen=True, slots=True)
class CreateCylinderTypeCommand(Command):
    tenant_id: uuid.UUID
    size_code: str
    hsn_code: str | None = None
    gst_rate_percent: Decimal | None = None


class CreateCylinderTypeUseCase:
    def __init__(self, repository: CylinderTypeRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: CreateCylinderTypeCommand) -> CylinderType:
        size = _require_size(command.size_code)
        await _require_size_not_added(self._repository, command.tenant_id, size)
        cylinder_type = CylinderType.from_size(uuid.uuid4(), command.tenant_id, size)
        if command.hsn_code is not None and command.gst_rate_percent is not None:
            cylinder_type.classify_for_gst(
                hsn_code=command.hsn_code, gst_rate_percent=command.gst_rate_percent
            )
        await self._repository.add(cylinder_type)
        await self._unit_of_work.commit()
        return cylinder_type


@dataclass(frozen=True, slots=True)
class UpdateCylinderTypeCommand(Command):
    """Anything left `None` stays as it is. HSN and rate go together."""

    tenant_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    size_code: str | None = None
    hsn_code: str | None = None
    gst_rate_percent: Decimal | None = None


class UpdateCylinderTypeUseCase:
    def __init__(self, repository: CylinderTypeRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: UpdateCylinderTypeCommand) -> CylinderType:
        if (command.hsn_code is None) != (command.gst_rate_percent is None):
            msg = "Enter both the HSN code and the GST rate."
            raise ValidationError(msg)
        cylinder_type = await _require_cylinder_type(self._repository, command.cylinder_type_id)

        if command.size_code is not None:
            size = _require_size(command.size_code)
            if size != cylinder_type.size:
                await _require_size_not_added(
                    self._repository, command.tenant_id, size, ignoring=cylinder_type.id
                )
                in_use = bool(await self._repository.used_in(cylinder_type.id))
                cylinder_type.change_size(size, in_use=in_use)
        if command.hsn_code is not None and command.gst_rate_percent is not None:
            cylinder_type.classify_for_gst(
                hsn_code=command.hsn_code, gst_rate_percent=command.gst_rate_percent
            )

        await self._repository.save(cylinder_type)
        await self._unit_of_work.commit()
        return cylinder_type


@dataclass(frozen=True, slots=True)
class GetCylinderTypeUsageQuery:
    cylinder_type_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class CylinderTypeUsage:
    used_in: tuple[str, ...]
    allowed_size_codes: tuple[str, ...]


class GetCylinderTypeUsageUseCase:
    def __init__(self, repository: CylinderTypeRepository) -> None:
        self._repository = repository

    async def execute(self, query: GetCylinderTypeUsageQuery) -> CylinderTypeUsage:
        cylinder_type = await _require_cylinder_type(self._repository, query.cylinder_type_id)
        used_in = tuple(await self._repository.used_in(cylinder_type.id))
        return CylinderTypeUsage(
            used_in=used_in,
            allowed_size_codes=tuple(
                size.code
                for size in CYLINDER_SIZES
                if cylinder_type.can_change_size_to(size, in_use=bool(used_in))
            ),
        )


@dataclass(frozen=True, slots=True)
class DeleteCylinderTypeCommand(Command):
    cylinder_type_id: uuid.UUID


class DeleteCylinderTypeUseCase:
    """Only a type nothing refers to can be deleted: orders, stock, prices
    and invoices must keep resolving the type they were recorded with.
    """

    def __init__(self, repository: CylinderTypeRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: DeleteCylinderTypeCommand) -> None:
        cylinder_type = await _require_cylinder_type(self._repository, command.cylinder_type_id)
        used_in = await self._repository.used_in(cylinder_type.id)
        if used_in:
            msg = (
                f"{cylinder_type.name} is used in {_in_words(used_in)}, so it cannot be "
                "deleted. Deactivate it instead."
            )
            raise ConflictError(msg, cylinder_type_id=str(cylinder_type.id))

        await self._repository.delete(cylinder_type)
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
class ClassifyCylinderTypeForGstCommand(Command):
    cylinder_type_id: uuid.UUID
    hsn_code: str
    gst_rate_percent: Decimal


class ClassifyCylinderTypeForGstUseCase:
    """Set the HSN code and GST rate this cylinder type is invoiced at
    (BR-16, BR-31). Until set, invoices for it are not generated.
    """

    def __init__(self, repository: CylinderTypeRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: ClassifyCylinderTypeForGstCommand) -> CylinderType:
        cylinder_type = await self._repository.get(command.cylinder_type_id)
        if cylinder_type is None:
            msg = f"No cylinder type visible with id {command.cylinder_type_id}."
            raise NotFoundError(msg, cylinder_type_id=str(command.cylinder_type_id))

        cylinder_type.classify_for_gst(
            hsn_code=command.hsn_code, gst_rate_percent=command.gst_rate_percent
        )

        await self._repository.save(cylinder_type)
        await self._unit_of_work.commit()
        return cylinder_type


@dataclass(frozen=True, slots=True)
class ListCylinderTypesQuery:
    tenant_id: uuid.UUID


class ListCylinderTypesUseCase:
    def __init__(self, repository: CylinderTypeRepository) -> None:
        self._repository = repository

    async def execute(self, query: ListCylinderTypesQuery) -> list[CylinderType]:
        return list(await self._repository.list_for_tenant(query.tenant_id))
