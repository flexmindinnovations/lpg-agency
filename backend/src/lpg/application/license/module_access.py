"""Which modules an agency can use — a super admin switches them per agency
(`lpg.domain.license.modules`). Every module is off until switched on."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command
from lpg.application.common.errors import ValidationError
from lpg.domain.license.modules import TOGGLEABLE_MODULES, is_module_key

if TYPE_CHECKING:
    import uuid
    from collections.abc import Mapping, Set

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
class SetModulesCommand(Command):
    tenant_id: uuid.UUID
    #: Module key to the state it should have. Modules left out keep theirs.
    changes: Mapping[str, bool]


class SetModulesUseCase:
    """Switches several of an agency's modules together: all of them or none.

    Dependencies are checked on the result, so the order of the changes does
    not matter, and a module can be switched on along with what it needs."""

    def __init__(self, repository: TenantModuleSettingRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: SetModulesCommand) -> None:
        for key in command.changes:
            if not is_module_key(key):
                msg = f"'{key}' is not a module that can be switched on or off."
                raise ValidationError(msg, field="modules")
        current = await self._repository.enabled_keys()
        switched_on = {key for key, enabled in command.changes.items() if enabled}
        result = (current | switched_on) - (command.changes.keys() - switched_on)
        _check_dependencies(result, command.changes)
        for module in TOGGLEABLE_MODULES:
            wanted = command.changes.get(module.key)
            if wanted is None or wanted == (module.key in current):
                continue
            await self._repository.set_enabled(command.tenant_id, module.key, enabled=wanted)
        await self._unit_of_work.commit()


def _check_dependencies(enabled: Set[str], changes: Mapping[str, bool]) -> None:
    """Refuses a change that would leave a module on without one it needs."""
    for module in TOGGLEABLE_MODULES:
        if module.key not in enabled:
            continue
        missing = [key for key in module.requires if key not in enabled]
        if changes.get(module.key) and missing:
            msg = f"Switch on {_names(missing)} too; {module.label} needs it."
            raise ValidationError(msg, field="modules")
        removed = [key for key in missing if changes.get(key) is False]
        if removed:
            msg = f"Switch off {module.label} too; it needs {_names(removed)}."
            raise ValidationError(msg, field="modules")


def _names(keys: list[str]) -> str:
    labels = {m.key: m.label for m in TOGGLEABLE_MODULES}
    return ", ".join(labels[key] for key in keys)
