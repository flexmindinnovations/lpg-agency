"""Unit tests for the `CylinderUnit` aggregate (Cylinder Identity, Phase 20
subsystem 3)."""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from lpg.domain.common.base import InvariantViolation
from lpg.domain.compliance.cylinder_unit import (
    CylinderConditionStatusChanged,
    CylinderCustodyChanged,
    CylinderReceived,
    CylinderRetired,
    CylinderRetiredError,
    CylinderStatutoryTestRecorded,
    CylinderUnit,
    CylinderUnitRegistered,
    InvalidCylinderConditionTransitionError,
    default_test_due_date,
)


def _unit(**overrides: object) -> CylinderUnit:
    kwargs: dict[str, object] = {
        "cylinder_unit_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "cylinder_type_id": uuid.uuid4(),
        "serial_number": "CYL-000001",
        "condition_status": "empty",
        "custody_type": "warehouse",
        "custody_ref_id": uuid.uuid4(),
    }
    kwargs.update(overrides)
    return CylinderUnit(**kwargs)  # type: ignore[arg-type]


class TestConstruction:
    def test_records_a_registered_event(self) -> None:
        unit = _unit()
        assert isinstance(unit.events[0], CylinderUnitRegistered)
        assert unit.is_retired is False

    def test_rejects_an_empty_serial_number(self) -> None:
        with pytest.raises(InvariantViolation, match="serial number must not be empty"):
            _unit(serial_number="  ")

    def test_rejects_an_unknown_condition_status(self) -> None:
        with pytest.raises(
            InvariantViolation,
            match="condition status .* is not valid",  # noqa: RUF043 -- intentional wildcard
        ):
            _unit(condition_status="molten")

    def test_rejects_an_unknown_custody_type(self) -> None:
        with pytest.raises(
            InvariantViolation,
            match="Custody type .* is not valid",  # noqa: RUF043
        ):
            _unit(custody_type="orbit", custody_ref_id=uuid.uuid4())

    def test_bottling_plant_custody_must_not_carry_a_ref_id(self) -> None:
        with pytest.raises(InvariantViolation, match="must not carry a custody_ref_id"):
            _unit(custody_type="bottling_plant", custody_ref_id=uuid.uuid4())

    def test_non_bottling_plant_custody_requires_a_ref_id(self) -> None:
        with pytest.raises(InvariantViolation, match="requires a custody_ref_id"):
            _unit(custody_type="vehicle", custody_ref_id=None)

    def test_bottling_plant_custody_with_no_ref_id_is_valid(self) -> None:
        unit = _unit(custody_type="bottling_plant", custody_ref_id=None)
        assert unit.custody_type == "bottling_plant"
        assert unit.custody_ref_id is None


class TestIsDueForTest:
    def test_a_unit_with_no_due_date_is_not_due(self) -> None:
        unit = _unit(test_due_date=None)
        assert unit.is_due_for_test(as_of=date(2030, 1, 1)) is False

    def test_a_unit_is_due_once_the_due_date_has_passed(self) -> None:
        unit = _unit(test_due_date=date(2026, 6, 1))
        assert unit.is_due_for_test(as_of=date(2026, 6, 1)) is True  # inclusive
        assert unit.is_due_for_test(as_of=date(2026, 7, 1)) is True
        assert unit.is_due_for_test(as_of=date(2026, 5, 31)) is False


class TestRecordStatutoryTest:
    def test_sets_last_tested_and_due_date_and_records_an_event(self) -> None:
        unit = _unit()
        performed_by = uuid.uuid4()
        unit.record_statutory_test(
            tested_at=date(2026, 1, 1), due_date=date(2028, 1, 1), performed_by=performed_by
        )
        assert unit.last_tested_at == date(2026, 1, 1)
        assert unit.test_due_date == date(2028, 1, 1)
        assert isinstance(unit.events[-1], CylinderStatutoryTestRecorded)

    def test_rejects_on_a_retired_unit(self) -> None:
        unit = _unit()
        unit.retire(performed_by=uuid.uuid4())
        with pytest.raises(CylinderRetiredError):
            unit.record_statutory_test(
                tested_at=date(2026, 1, 1), due_date=date(2028, 1, 1), performed_by=uuid.uuid4()
            )


class TestMoveCustody:
    def test_updates_custody_and_records_an_event(self) -> None:
        unit = _unit(custody_type="warehouse")
        vehicle_id = uuid.uuid4()
        unit.move_custody(
            custody_type="vehicle", custody_ref_id=vehicle_id, performed_by=uuid.uuid4()
        )
        assert unit.custody_type == "vehicle"
        assert unit.custody_ref_id == vehicle_id
        assert isinstance(unit.events[-1], CylinderCustodyChanged)

    def test_moving_to_bottling_plant_clears_the_ref_id(self) -> None:
        unit = _unit()
        unit.move_custody(
            custody_type="bottling_plant", custody_ref_id=None, performed_by=uuid.uuid4()
        )
        assert unit.custody_type == "bottling_plant"
        assert unit.custody_ref_id is None

    def test_moving_to_bottling_plant_with_a_ref_id_is_rejected(self) -> None:
        unit = _unit()
        with pytest.raises(InvariantViolation, match="must not carry a custody_ref_id"):
            unit.move_custody(
                custody_type="bottling_plant",
                custody_ref_id=uuid.uuid4(),
                performed_by=uuid.uuid4(),
            )


class TestChangeConditionStatus:
    @pytest.mark.parametrize(
        ("start", "target"),
        [
            ("filled", "empty"),
            ("filled", "leakage"),
            ("empty", "damaged"),
            ("empty", "leakage"),
            ("damaged", "quarantine"),
            ("leakage", "quarantine"),
            ("quarantine", "repair"),
            ("quarantine", "scrap"),
            ("repair", "empty"),
        ],
    )
    def test_allowed_transitions(self, start: str, target: str) -> None:
        unit = _unit(condition_status=start)
        unit.change_condition_status(new_status=target, performed_by=uuid.uuid4())
        assert unit.condition_status == target
        assert isinstance(unit.events[-1], CylinderConditionStatusChanged)

    def test_repair_does_not_go_directly_back_to_filled(self) -> None:
        # A repaired unit re-enters the fillable pool empty, not filled —
        # it must go through the Rule-26-gated receive() to be charged
        # again, same as any other empty unit.
        unit = _unit(condition_status="repair")
        with pytest.raises(InvalidCylinderConditionTransitionError):
            unit.change_condition_status(new_status="filled", performed_by=uuid.uuid4())

    def test_scrap_is_terminal(self) -> None:
        unit = _unit(condition_status="scrap")
        with pytest.raises(InvalidCylinderConditionTransitionError):
            unit.change_condition_status(new_status="quarantine", performed_by=uuid.uuid4())

    def test_carries_an_optional_reason_on_the_event(self) -> None:
        unit = _unit(condition_status="filled")
        unit.change_condition_status(
            new_status="leakage", performed_by=uuid.uuid4(), reason="valve failure on inspection"
        )
        event = unit.events[-1]
        assert isinstance(event, CylinderConditionStatusChanged)
        assert event.reason == "valve failure on inspection"


class TestReceive:
    def test_charges_an_empty_unit_and_moves_it_to_the_warehouse(self) -> None:
        unit = _unit(condition_status="empty", custody_type="vehicle")
        warehouse_id = uuid.uuid4()
        unit.receive(warehouse_id=warehouse_id, performed_by=uuid.uuid4())
        assert unit.condition_status == "filled"
        assert unit.custody_type == "warehouse"
        assert unit.custody_ref_id == warehouse_id
        assert isinstance(unit.events[-1], CylinderReceived)

    def test_rejects_a_unit_that_is_not_empty(self) -> None:
        unit = _unit(condition_status="quarantine")
        with pytest.raises(InvalidCylinderConditionTransitionError):
            unit.receive(warehouse_id=uuid.uuid4(), performed_by=uuid.uuid4())

    def test_does_not_itself_enforce_the_due_for_test_rule(self) -> None:
        # Rule 26 enforcement is an application-layer concern
        # (ReceiveCylinderUnitUseCase) — the domain command stays pure and
        # will happily receive an overdue unit if called directly. This
        # test pins that boundary so it isn't accidentally moved later
        # without a deliberate decision.
        unit = _unit(condition_status="empty", test_due_date=date(2020, 1, 1))
        unit.receive(warehouse_id=uuid.uuid4(), performed_by=uuid.uuid4())
        assert unit.condition_status == "filled"


class TestRetire:
    def test_sets_is_retired_and_records_an_event(self) -> None:
        unit = _unit()
        unit.retire(performed_by=uuid.uuid4())
        assert unit.is_retired is True
        assert isinstance(unit.events[-1], CylinderRetired)

    def test_a_retired_unit_rejects_further_mutation(self) -> None:
        unit = _unit()
        unit.retire(performed_by=uuid.uuid4())
        with pytest.raises(CylinderRetiredError):
            unit.change_condition_status(new_status="empty", performed_by=uuid.uuid4())
        with pytest.raises(CylinderRetiredError):
            unit.move_custody(
                custody_type="warehouse", custody_ref_id=uuid.uuid4(), performed_by=uuid.uuid4()
            )
        with pytest.raises(CylinderRetiredError):
            unit.retire(performed_by=uuid.uuid4())


class TestDefaultTestDueDate:
    def test_adds_whole_months(self) -> None:
        assert default_test_due_date(date(2026, 1, 15), 6) == date(2026, 7, 15)

    def test_rolls_over_year_boundaries(self) -> None:
        assert default_test_due_date(date(2026, 11, 1), 3) == date(2027, 2, 1)

    def test_clamps_the_day_for_a_shorter_target_month(self) -> None:
        # 31 Jan + 1 month -> Feb has no 31st.
        assert default_test_due_date(date(2026, 1, 31), 1) == date(2026, 2, 28)

    def test_rejects_a_non_positive_interval(self) -> None:
        with pytest.raises(InvariantViolation, match="must be positive"):
            default_test_due_date(date(2026, 1, 1), 0)
