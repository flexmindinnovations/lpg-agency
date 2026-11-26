"""Module access — every module is off until a super admin switches it on."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from lpg.api.v1.dependencies.license import require_module_access
from lpg.application.common.errors import ModuleDisabledError, ValidationError
from lpg.application.license.module_access import (
    ListModulesUseCase,
    SetModulesCommand,
    SetModulesUseCase,
)
from lpg.domain.license.modules import (
    MODULE_KEYS,
    TOGGLEABLE_MODULES,
    module_for_path,
)


def _repository(enabled: frozenset[str] = frozenset()) -> MagicMock:
    repository = MagicMock()
    repository.enabled_keys = AsyncMock(return_value=enabled)
    repository.set_enabled = AsyncMock()
    return repository


def _request(path: str) -> MagicMock:
    return MagicMock(url=MagicMock(path=path))


def test_the_catalog_is_consistent() -> None:
    assert all(m.label and m.description and m.group for m in TOGGLEABLE_MODULES)
    seen: set[str] = set()
    for module in TOGGLEABLE_MODULES:
        # listed dependencies first, and every dependency is a real module
        assert set(module.requires) <= seen, module.key
        seen.add(module.key)
    assert seen == MODULE_KEYS


@pytest.mark.parametrize(
    ("path", "module"),
    [
        ("/customers", "customers"),
        ("/customers/abc/ledger", "customers"),
        ("/customers/onboarding-drafts", "customers"),
        ("/orders/123/dispatch", "orders"),
        ("/routes/1/weighment", "dispatch"),
        ("/drivers/me", "drivers"),
        ("/vehicles/1/details", "vehicles"),
        ("/vehicles/1/collections", "inventory"),
        ("/warehouses/1/goods-receipt-notes", "inventory"),
        ("/goods-receipt-notes/1/weighment", "inventory"),
        ("/inventory-locations/warehouse/1/balance", "inventory"),
        ("/inventory/reorder-policy", "inventory"),
        ("/scales", "scales"),
        ("/cylinder-units/5/label", "cylinder_units"),
        ("/compliance-documents", "compliance_calendar"),
        ("/invoices/1", "invoices"),
        ("/print-jobs", "invoices"),
        ("/cash-handovers", "cash_handovers"),
        ("/complaints", "complaints"),
        ("/reporting/sales", "reports"),
        ("/tdt-rating/quarterly", "reports"),
        ("/ai/query", "ai_command_center"),
    ],
)
def test_paths_map_to_their_module(path: str, module: str) -> None:
    assert module_for_path(path) == module


@pytest.mark.parametrize(
    "path",
    [
        "/admin/modules",
        "/admin/warehouses",
        "/notifications",
        "/dashboard/summary",
        "/warehouses/1/documents",
        "/tenant/documents",
        "/payments/razorpay/webhook/abc",
        "/customersx",
    ],
)
def test_always_on_paths_belong_to_no_module(path: str) -> None:
    assert module_for_path(path) is None


async def test_every_module_is_off_by_default() -> None:
    modules = await ListModulesUseCase(_repository()).execute()
    assert [m.key for m in modules] == [m.key for m in TOGGLEABLE_MODULES]
    assert not any(m.enabled for m in modules)


async def test_a_switched_on_module_is_reported_on() -> None:
    modules = await ListModulesUseCase(_repository(frozenset({"scales"}))).execute()
    assert {m.key for m in modules if m.enabled} == {"scales"}


async def _set(
    changes: dict[str, bool], enabled: frozenset[str] = frozenset()
) -> tuple[MagicMock, MagicMock]:
    repository, unit_of_work = _repository(enabled), MagicMock(commit=AsyncMock())
    await SetModulesUseCase(repository, unit_of_work).execute(
        SetModulesCommand(tenant_id=uuid.uuid4(), changes=changes)
    )
    return repository, unit_of_work


def _saved(repository: MagicMock) -> list[tuple[str, bool]]:
    return [(c.args[1], c.kwargs["enabled"]) for c in repository.set_enabled.await_args_list]


async def test_switching_modules_saves_them_and_commits_once() -> None:
    repository, unit_of_work = await _set(
        {"scales": True, "reports": False}, frozenset({"reports"})
    )

    assert sorted(_saved(repository)) == [("reports", False), ("scales", True)]
    unit_of_work.commit.assert_awaited_once()


async def test_only_modules_that_change_are_written() -> None:
    repository, _ = await _set({"scales": True, "reports": True}, frozenset({"scales"}))

    assert _saved(repository) == [("reports", True)]


async def test_a_module_can_be_switched_on_with_what_it_needs_in_any_order() -> None:
    repository, _ = await _set({"orders": True, "inventory": True, "customers": True})

    assert sorted(_saved(repository)) == [
        ("customers", True),
        ("inventory", True),
        ("orders", True),
    ]


async def test_a_module_and_what_it_needs_can_be_switched_off_together() -> None:
    repository, _ = await _set(
        {"customers": False, "orders": False}, frozenset({"customers", "orders"})
    )

    assert sorted(_saved(repository)) == [("customers", False), ("orders", False)]


@pytest.mark.parametrize(
    ("changes", "enabled", "message"),
    [
        ({"scales": True, "nope": True}, frozenset(), "not a module"),
        (
            {"scales": True, "dispatch": True},
            frozenset({"customers"}),
            "Switch on Orders, Drivers, Vehicles too; Dispatch needs it",
        ),
        (
            {"customers": False},
            frozenset({"customers", "inventory", "orders"}),
            "Switch off Orders too; it needs Customers",
        ),
        # No booking can succeed without stock, so Orders never runs without Inventory.
        (
            {"orders": True},
            frozenset({"customers"}),
            "Switch on Inventory too; Orders needs it",
        ),
        (
            {"inventory": False},
            frozenset({"customers", "inventory", "orders"}),
            "Switch off Orders too; it needs Inventory",
        ),
    ],
)
async def test_a_refused_change_saves_nothing(
    changes: dict[str, bool], enabled: frozenset[str], message: str
) -> None:
    repository, unit_of_work = _repository(enabled), MagicMock(commit=AsyncMock())

    with pytest.raises(ValidationError, match=message):
        await SetModulesUseCase(repository, unit_of_work).execute(
            SetModulesCommand(tenant_id=uuid.uuid4(), changes=changes)
        )

    repository.set_enabled.assert_not_awaited()
    unit_of_work.commit.assert_not_awaited()


async def test_the_gate_blocks_a_module_that_is_not_on() -> None:
    with pytest.raises(ModuleDisabledError) as raised:
        await require_module_access(_request("/api/v1/scales"), _repository())
    assert raised.value.http_status == 403
    assert raised.value.error_code == "MODULE_DISABLED"

    await require_module_access(_request("/api/v1/scales"), _repository(frozenset({"scales"})))


async def test_the_gate_lets_always_on_paths_through() -> None:
    repository = _repository()
    await require_module_access(_request("/api/v1/dashboard/summary"), repository)
    repository.enabled_keys.assert_not_awaited()
