"""Module visibility — every module is on unless a super admin switched it off."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from lpg.api.v1.dependencies.license import require_module
from lpg.application.common.errors import ModuleDisabledError, ValidationError
from lpg.application.license.module_access import (
    ListModulesUseCase,
    SetModuleEnabledCommand,
    SetModuleEnabledUseCase,
)
from lpg.domain.license.modules import MODULE_KEYS, TOGGLEABLE_MODULES


def _repository(disabled: frozenset[str] = frozenset()) -> MagicMock:
    repository = MagicMock()
    repository.disabled_keys = AsyncMock(return_value=disabled)
    repository.set_enabled = AsyncMock()
    return repository


def test_the_catalog_has_the_three_requested_modules() -> None:
    assert {"ai_command_center", "scales", "cylinder_units"} == MODULE_KEYS
    assert all(m.label and m.description for m in TOGGLEABLE_MODULES)


async def test_every_module_is_on_by_default() -> None:
    modules = await ListModulesUseCase(_repository()).execute()
    assert [m.key for m in modules] == [m.key for m in TOGGLEABLE_MODULES]
    assert all(m.enabled for m in modules)


async def test_a_switched_off_module_is_reported_off() -> None:
    modules = await ListModulesUseCase(_repository(frozenset({"scales"}))).execute()
    assert {m.key: m.enabled for m in modules} == {
        "ai_command_center": True,
        "scales": False,
        "cylinder_units": True,
    }


async def test_switching_a_module_saves_and_commits() -> None:
    repository, unit_of_work = _repository(), MagicMock(commit=AsyncMock())
    tenant_id = uuid.uuid4()

    await SetModuleEnabledUseCase(repository, unit_of_work).execute(
        SetModuleEnabledCommand(tenant_id=tenant_id, module_key="scales", enabled=False)
    )

    repository.set_enabled.assert_awaited_once_with(tenant_id, "scales", enabled=False)
    unit_of_work.commit.assert_awaited_once()


async def test_an_unknown_module_is_refused() -> None:
    repository, unit_of_work = _repository(), MagicMock(commit=AsyncMock())

    with pytest.raises(ValidationError):
        await SetModuleEnabledUseCase(repository, unit_of_work).execute(
            SetModuleEnabledCommand(tenant_id=uuid.uuid4(), module_key="orders", enabled=False)
        )

    repository.set_enabled.assert_not_awaited()
    unit_of_work.commit.assert_not_awaited()


async def test_require_module_blocks_only_a_disabled_module() -> None:
    check = require_module("scales")

    await check(_repository(frozenset({"cylinder_units"})))  # a different module is off: fine
    with pytest.raises(ModuleDisabledError) as raised:
        await check(_repository(frozenset({"scales"})))
    assert raised.value.http_status == 403
    assert raised.value.error_code == "MODULE_DISABLED"
