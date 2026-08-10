"""`Branch`/`Warehouse` domain aggregates — no database required."""

from __future__ import annotations

import uuid

import pytest

from lpg.domain.common.base import InvariantViolation
from lpg.domain.tenant.branch import Branch, BranchRenamed
from lpg.domain.tenant.warehouse import Warehouse, WarehouseRenamed


def _make_branch(**overrides: object) -> Branch:
    defaults: dict[str, object] = {
        "branch_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "name": "Nashik West Branch",
        "region": "Maharashtra",
    }
    defaults.update(overrides)
    return Branch(**defaults)  # type: ignore[arg-type]


def _make_warehouse(**overrides: object) -> Warehouse:
    defaults: dict[str, object] = {
        "warehouse_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "branch_id": uuid.uuid4(),
        "name": "Nashik Central Warehouse",
        "address_line": "Plot 12, MIDC Ambad",
    }
    defaults.update(overrides)
    return Warehouse(**defaults)  # type: ignore[arg-type]


class TestBranch:
    def test_rename_changes_the_name_and_records_an_event(self) -> None:
        branch = _make_branch()

        branch.rename("Nashik East Branch")

        assert branch.name == "Nashik East Branch"
        assert [type(e) for e in branch.events] == [BranchRenamed]

    def test_rename_rejects_an_empty_name(self) -> None:
        branch = _make_branch()

        with pytest.raises(InvariantViolation):
            branch.rename("   ")

    def test_set_region_accepts_none_to_clear_it(self) -> None:
        branch = _make_branch(region="Maharashtra")

        branch.set_region(None)

        assert branch.region is None

    def test_set_region_strips_whitespace(self) -> None:
        branch = _make_branch()

        branch.set_region("  Gujarat  ")

        assert branch.region == "Gujarat"


class TestWarehouse:
    def test_rename_changes_the_name_and_records_an_event(self) -> None:
        warehouse = _make_warehouse()

        warehouse.rename("Nashik North Warehouse")

        assert warehouse.name == "Nashik North Warehouse"
        assert [type(e) for e in warehouse.events] == [WarehouseRenamed]

    def test_rename_rejects_an_empty_name(self) -> None:
        warehouse = _make_warehouse()

        with pytest.raises(InvariantViolation):
            warehouse.rename("")

    def test_relocate_changes_the_address(self) -> None:
        warehouse = _make_warehouse()

        warehouse.relocate("Plot 45, MIDC Satpur")

        assert warehouse.address_line == "Plot 45, MIDC Satpur"

    def test_relocate_rejects_an_empty_address(self) -> None:
        warehouse = _make_warehouse()

        with pytest.raises(InvariantViolation):
            warehouse.relocate("   ")
