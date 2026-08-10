"""`SetTenantConfigurationUseCase` / `GetEffectiveTenantConfigurationUseCase`
/ `ListTenantConfigurationUseCase`.

"Setting" a config value always inserts a new historized row — see
`lpg.domain.tenant.tenant_configuration`'s module docstring for why there is
no update/mutate use case here.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from lpg.application.common.cqrs import Command
from lpg.domain.tenant.tenant_configuration import TenantConfiguration, TenantConfigurationResolver

if TYPE_CHECKING:
    from lpg.application.common.ports import UnitOfWork
    from lpg.application.tenant.ports import TenantConfigurationRepository


@dataclass(frozen=True, slots=True)
class SetTenantConfigurationCommand(Command):
    tenant_id: uuid.UUID
    config_key: str
    config_value: Any
    effective_from: datetime | None = None


class SetTenantConfigurationUseCase:
    def __init__(self, repository: TenantConfigurationRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: SetTenantConfigurationCommand) -> TenantConfiguration:
        config = TenantConfiguration(
            uuid.uuid4(),
            command.tenant_id,
            command.config_key,
            command.config_value,
            command.effective_from or datetime.now(UTC),
        )
        await self._repository.add(config)
        await self._unit_of_work.commit()
        return config


@dataclass(frozen=True, slots=True)
class GetEffectiveTenantConfigurationQuery:
    tenant_id: uuid.UUID
    config_key: str
    at: datetime | None = None


class GetEffectiveTenantConfigurationUseCase:
    def __init__(self, repository: TenantConfigurationRepository) -> None:
        self._repository = repository

    async def execute(
        self, query: GetEffectiveTenantConfigurationQuery
    ) -> TenantConfiguration | None:
        entries = await self._repository.list_for_tenant_and_key(query.tenant_id, query.config_key)
        return TenantConfigurationResolver.resolve(
            entries, query.config_key, query.at or datetime.now(UTC)
        )


@dataclass(frozen=True, slots=True)
class ListTenantConfigurationQuery:
    tenant_id: uuid.UUID


class ListTenantConfigurationUseCase:
    def __init__(self, repository: TenantConfigurationRepository) -> None:
        self._repository = repository

    async def execute(self, query: ListTenantConfigurationQuery) -> list[TenantConfiguration]:
        return list(await self._repository.list_for_tenant(query.tenant_id))
