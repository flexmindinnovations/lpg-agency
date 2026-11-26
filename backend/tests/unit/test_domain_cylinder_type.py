"""`CylinderType` aggregate and the standard size list — no database required."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from lpg.domain.common.base import InvariantViolation
from lpg.domain.tenant.cylinder_catalog import (
    COMMERCIAL,
    CYLINDER_SIZES,
    DOMESTIC,
    CylinderSize,
    size_by_code,
)
from lpg.domain.tenant.cylinder_type import CylinderType, CylinderTypeSizeChanged
from lpg.infrastructure.persistence.database import Base
from lpg.infrastructure.persistence.repositories.tenant import _CYLINDER_TYPE_REFERENCES


def _make_cylinder_type(**overrides: object) -> CylinderType:
    defaults: dict[str, object] = {
        "cylinder_type_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "name": "14.2 kg Domestic",
        "weight_kg": Decimal("14.20"),
    }
    defaults.update(overrides)
    return CylinderType(**defaults)  # type: ignore[arg-type]


def _size(code: str) -> CylinderSize:
    size = size_by_code(code)
    assert size is not None
    return size


class TestStandardSizes:
    def test_is_the_indianoil_and_hpcl_list(self) -> None:
        by_category = {
            category: [s.weight_kg for s in CYLINDER_SIZES if s.category == category]
            for category in (DOMESTIC, COMMERCIAL)
        }

        assert by_category[DOMESTIC] == [Decimal(w) for w in ("5", "10", "14.2")]
        assert by_category[COMMERCIAL] == [
            Decimal(w) for w in ("2", "5", "19", "35", "47.5", "425")
        ]

    def test_codes_and_names_are_unique(self) -> None:
        assert len({s.code for s in CYLINDER_SIZES}) == len(CYLINDER_SIZES)
        assert len({s.name.casefold() for s in CYLINDER_SIZES}) == len(CYLINDER_SIZES)

    def test_a_stored_record_matches_by_name_and_weight(self) -> None:
        # The database returns two decimal places.
        assert _make_cylinder_type().size == _size("domestic_14_2")

    @pytest.mark.parametrize(
        ("name", "weight"), [("19KG_Domestic", "19"), ("14.2 kg Domestic", "19")]
    )
    def test_anything_else_is_off_the_list(self, name: str, weight: str) -> None:
        assert _make_cylinder_type(name=name, weight_kg=Decimal(weight)).size is None

    def test_a_new_type_takes_its_name_and_weight_from_the_size(self) -> None:
        cylinder_type = CylinderType.from_size(uuid.uuid4(), uuid.uuid4(), _size("commercial_19"))

        assert (cylinder_type.name, cylinder_type.weight_kg) == ("19 kg Commercial", Decimal(19))
        assert cylinder_type.is_active


class TestChangeSize:
    def test_an_unused_type_takes_any_size(self) -> None:
        cylinder_type = _make_cylinder_type()

        cylinder_type.change_size(_size("commercial_47_5"), in_use=False)

        assert cylinder_type.name == "47.5 kg Commercial"
        assert cylinder_type.weight_kg == Decimal("47.5")
        assert [type(e) for e in cylinder_type.events] == [CylinderTypeSizeChanged]

    def test_a_used_type_on_the_list_keeps_its_size(self) -> None:
        cylinder_type = _make_cylinder_type(name="5 kg Domestic", weight_kg=Decimal(5))

        # Same weight, but it would turn household sales into commercial ones.
        with pytest.raises(InvariantViolation):
            cylinder_type.change_size(_size("commercial_5_ftl"), in_use=True)

        assert cylinder_type.name == "5 kg Domestic"

    def test_keeping_the_same_size_is_always_fine(self) -> None:
        cylinder_type = _make_cylinder_type()

        cylinder_type.change_size(_size("domestic_14_2"), in_use=True)

        assert not cylinder_type.events

    def test_a_used_off_list_record_takes_a_list_size_of_its_weight(self) -> None:
        cylinder_type = _make_cylinder_type(name="19KG_Domestic", weight_kg=Decimal(19))

        cylinder_type.change_size(_size("commercial_19"), in_use=True)

        assert cylinder_type.name == "19 kg Commercial"

    def test_a_used_off_list_record_cannot_change_weight(self) -> None:
        cylinder_type = _make_cylinder_type(name="19KG_Domestic", weight_kg=Decimal(19))

        with pytest.raises(InvariantViolation):
            cylinder_type.change_size(_size("domestic_14_2"), in_use=True)


class TestDeletionGuard:
    def test_every_table_that_records_a_cylinder_type_is_checked(self) -> None:
        """A table missing here would let its cylinder type be deleted."""
        checked = {
            model.__table__.fullname for _, models in _CYLINDER_TYPE_REFERENCES for model in models
        }
        recording = {
            table.fullname
            for table in Base.metadata.tables.values()
            if "cylinder_type_id" in table.columns
        }

        assert checked == recording


class TestActivation:
    def test_defaults_to_active(self) -> None:
        assert _make_cylinder_type().is_active is True

    def test_deactivate_then_activate_round_trips(self) -> None:
        cylinder_type = _make_cylinder_type()

        cylinder_type.deactivate()
        assert cylinder_type.is_active is False

        cylinder_type.activate()
        assert cylinder_type.is_active is True
