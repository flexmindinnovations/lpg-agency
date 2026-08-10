"""`CylinderType` domain aggregate — no database required."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from lpg.domain.common.base import InvariantViolation
from lpg.domain.tenant.cylinder_type import CylinderType, CylinderTypeRenamed


def _make_cylinder_type(**overrides: object) -> CylinderType:
    defaults: dict[str, object] = {
        "cylinder_type_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "name": "14.2kg Domestic",
        "weight_kg": Decimal("14.20"),
    }
    defaults.update(overrides)
    return CylinderType(**defaults)  # type: ignore[arg-type]


class TestConstruction:
    def test_defaults_to_active(self) -> None:
        cylinder_type = _make_cylinder_type()

        assert cylinder_type.is_active is True


class TestRename:
    def test_changes_the_name_and_records_an_event(self) -> None:
        cylinder_type = _make_cylinder_type()

        cylinder_type.rename("19kg Commercial")

        assert cylinder_type.name == "19kg Commercial"
        assert [type(e) for e in cylinder_type.events] == [CylinderTypeRenamed]

    def test_rejects_an_empty_name(self) -> None:
        cylinder_type = _make_cylinder_type()

        with pytest.raises(InvariantViolation):
            cylinder_type.rename("   ")


class TestAdjustWeight:
    def test_changes_the_weight(self) -> None:
        cylinder_type = _make_cylinder_type()

        cylinder_type.adjust_weight(Decimal("19.00"))

        assert cylinder_type.weight_kg == Decimal("19.00")

    def test_rejects_zero_weight(self) -> None:
        cylinder_type = _make_cylinder_type()

        with pytest.raises(InvariantViolation):
            cylinder_type.adjust_weight(Decimal("0"))

    def test_rejects_negative_weight(self) -> None:
        cylinder_type = _make_cylinder_type()

        with pytest.raises(InvariantViolation):
            cylinder_type.adjust_weight(Decimal("-1"))


class TestActivation:
    def test_deactivate_then_activate_round_trips(self) -> None:
        cylinder_type = _make_cylinder_type()

        cylinder_type.deactivate()
        assert cylinder_type.is_active is False

        cylinder_type.activate()
        assert cylinder_type.is_active is True
