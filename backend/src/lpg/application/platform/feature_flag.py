"""Feature-flag use cases.

Platform-level mutations (`CreateFeatureFlagUseCase`,
`SetFeatureFlagEnabledByDefaultUseCase`, `SetFeatureFlagRolloutPercentageUseCase`,
`ScheduleFeatureFlagUseCase`) are gated by `require_live_permission
("feature_flags:manage_platform")` at the API layer — super_admin only, live
-checked, the same high-sensitivity pattern `reconciliation:approve` uses.
Tenant-level overrides (`SetTenantFeatureFlagOverrideUseCase`) need only
`feature_flags:manage_tenant` (claims-based, `agency_admin`).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command
from lpg.application.common.errors import NotFoundError
from lpg.domain.platform.feature_flag import FeatureFlag, FeatureFlagOverride, FeatureFlagService

if TYPE_CHECKING:
    from lpg.application.common.ports import UnitOfWork
    from lpg.application.platform.ports import FeatureFlagOverrideRepository, FeatureFlagRepository


@dataclass(frozen=True, slots=True)
class CreateFeatureFlagCommand(Command):
    key: str
    description: str
    is_enabled_by_default: bool = False
    rollout_percentage: int | None = None


class CreateFeatureFlagUseCase:
    def __init__(self, repository: FeatureFlagRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: CreateFeatureFlagCommand) -> FeatureFlag:
        flag = FeatureFlag(
            command.key,
            command.description,
            is_enabled_by_default=command.is_enabled_by_default,
            rollout_percentage=command.rollout_percentage,
        )
        await self._repository.add(flag)
        await self._unit_of_work.commit()
        return flag


@dataclass(frozen=True, slots=True)
class SetFeatureFlagEnabledByDefaultCommand(Command):
    key: str
    enabled: bool


class SetFeatureFlagEnabledByDefaultUseCase:
    def __init__(self, repository: FeatureFlagRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: SetFeatureFlagEnabledByDefaultCommand) -> None:
        flag = await self._repository.get(command.key)
        if flag is None:
            msg = f"No feature flag with key '{command.key}'."
            raise NotFoundError(msg, key=command.key)

        flag.set_enabled_by_default(enabled=command.enabled)

        await self._repository.save(flag)
        await self._unit_of_work.commit()


@dataclass(frozen=True, slots=True)
class SetFeatureFlagRolloutPercentageCommand(Command):
    key: str
    rollout_percentage: int | None


class SetFeatureFlagRolloutPercentageUseCase:
    def __init__(self, repository: FeatureFlagRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: SetFeatureFlagRolloutPercentageCommand) -> None:
        flag = await self._repository.get(command.key)
        if flag is None:
            msg = f"No feature flag with key '{command.key}'."
            raise NotFoundError(msg, key=command.key)

        flag.set_rollout_percentage(command.rollout_percentage)

        await self._repository.save(flag)
        await self._unit_of_work.commit()


@dataclass(frozen=True, slots=True)
class ScheduleFeatureFlagCommand(Command):
    key: str
    starts_at: datetime | None
    ends_at: datetime | None


class ScheduleFeatureFlagUseCase:
    def __init__(self, repository: FeatureFlagRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: ScheduleFeatureFlagCommand) -> None:
        flag = await self._repository.get(command.key)
        if flag is None:
            msg = f"No feature flag with key '{command.key}'."
            raise NotFoundError(msg, key=command.key)

        flag.schedule(starts_at=command.starts_at, ends_at=command.ends_at)

        await self._repository.save(flag)
        await self._unit_of_work.commit()


@dataclass(frozen=True, slots=True)
class ListFeatureFlagsQuery:
    pass


class ListFeatureFlagsUseCase:
    def __init__(self, repository: FeatureFlagRepository) -> None:
        self._repository = repository

    async def execute(self, query: ListFeatureFlagsQuery) -> list[FeatureFlag]:
        del query
        return list(await self._repository.list_all())


@dataclass(frozen=True, slots=True)
class SetTenantFeatureFlagOverrideCommand(Command):
    tenant_id: uuid.UUID
    flag_key: str
    enabled: bool


class SetTenantFeatureFlagOverrideUseCase:
    """Creates the override on first use, updates it on every call after —
    a tenant only ever has one override per flag (`uq_feature_flag_override_
    tenant_flag`), so "set" always means "the current override state is
    exactly this," not "add another override."
    """

    def __init__(
        self,
        override_repository: FeatureFlagOverrideRepository,
        flag_repository: FeatureFlagRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._override_repository = override_repository
        self._flag_repository = flag_repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: SetTenantFeatureFlagOverrideCommand) -> None:
        flag = await self._flag_repository.get(command.flag_key)
        if flag is None:
            msg = f"No feature flag with key '{command.flag_key}'."
            raise NotFoundError(msg, key=command.flag_key)

        existing = await self._override_repository.get_for_tenant_and_flag(
            command.tenant_id, command.flag_key
        )
        if existing is not None:
            existing.set_enabled(enabled=command.enabled)
            await self._override_repository.save(existing)
        else:
            override = FeatureFlagOverride(
                uuid.uuid4(), command.tenant_id, command.flag_key, is_enabled=command.enabled
            )
            await self._override_repository.add(override)

        await self._unit_of_work.commit()


@dataclass(frozen=True, slots=True)
class IsFeatureFlagEnabledQuery:
    tenant_id: uuid.UUID
    flag_key: str
    at: datetime | None = None


class IsFeatureFlagEnabledUseCase:
    def __init__(
        self,
        flag_repository: FeatureFlagRepository,
        override_repository: FeatureFlagOverrideRepository,
    ) -> None:
        self._flag_repository = flag_repository
        self._override_repository = override_repository

    async def execute(self, query: IsFeatureFlagEnabledQuery) -> bool:
        flag = await self._flag_repository.get(query.flag_key)
        override = await self._override_repository.get_for_tenant_and_flag(
            query.tenant_id, query.flag_key
        )
        return FeatureFlagService.is_enabled(
            flag, override, query.tenant_id, at=query.at or datetime.now(UTC)
        )
