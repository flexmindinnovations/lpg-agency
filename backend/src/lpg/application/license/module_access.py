"""Which modules an agency can use — a super admin switches them per agency
(`lpg.domain.license.modules`). Every module is off until switched on."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command
from lpg.application.common.errors import ValidationError
from lpg.domain.license.modules import (
    TOGGLEABLE_MODULES,
    is_module_key,
    modules_needing,
    requirements_of,
)

if TYPE_CHECKING:
    import uuid

    from lpg.application.common.ports import UnitOfWork
    from lpg.application.license.ports import TenantModuleSettingRepository


@dataclass(frozen=True, slots=True)
class ModuleState:
    key: str
    label: str
    description: str
    group: str
    requires: tuple[str, ...]
    enabled: bool


class ListModulesUseCase:
    """The agency's modules with their on/off state. Scoped to the unit of
    work's tenant, so it serves both the agency's own sidebar and a super
    admin looking at one agency."""

    def __init__(self, repository: TenantModuleSettingRepository) -> None:
        self._repository = repository

    async def execute(self) -> list[ModuleState]:
        enabled = await self._repository.enabled_keys()
        return [
            ModuleState(
                m.key, m.label, m.description, m.group, m.requires, enabled=m.key in enabled
            )
            for m in TOGGLEABLE_MODULES
        ]


@dataclass(frozen=True, slots=True)
class SetModuleEnabledCommand(Command):
    tenant_id: uuid.UUID
    module_key: str
    enabled: bool


class SetModuleEnabledUseCase:
    def __init__(self, repository: TenantModuleSettingRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: SetModuleEnabledCommand) -> None:
        if not is_module_key(command.module_key):
            msg = f"'{command.module_key}' is not a module that can be switched on or off."
            raise ValidationError(msg, field="module_key")
        enabled = await self._repository.enabled_keys()
        if command.enabled:
            missing = [key for key in requirements_of(command.module_key) if key not in enabled]
            if missing:
                msg = f"Switch on {_names(missing)} first; this module needs it."
                raise ValidationError(msg, field="module_key")
        else:
            blocking = [key for key in modules_needing(command.module_key) if key in enabled]
            if blocking:
                msg = f"Switch off {_names(blocking)} first; it needs this module."
                raise ValidationError(msg, field="module_key")
        await self._repository.set_enabled(
            command.tenant_id, command.module_key, enabled=command.enabled
        )
        await self._unit_of_work.commit()


def _names(keys: list[str]) -> str:
    labels = {m.key: m.label for m in TOGGLEABLE_MODULES}
    return ", ".join(labels[key] for key in keys)
