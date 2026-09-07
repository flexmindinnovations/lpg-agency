"""Unit tests for WeighmentRecord and compute_weighment_result (Weighment
Part 2)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from lpg.domain.common.base import InvariantViolation
from lpg.domain.compliance.weighment_record import (
    WeighmentRecord,
    compute_weighment_result,
)


def _record(**overrides: object) -> WeighmentRecord:
    kwargs: dict[str, object] = {
        "id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "scale_id": uuid.uuid4(),
        "context": "goods_receipt_sample",
        "reference_type": "grn",
        "reference_id": uuid.uuid4(),
        "cylinder_type_id": uuid.uuid4(),
        "total_cylinders_in_batch": 100,
        "cylinders_checked": 10,
        "underweight_cylinder_count": 0,
        "tolerance_grams_applied": 150,
        "result": "pass",
        "recorded_by": uuid.uuid4(),
        "recorded_at": datetime.now(UTC),
    }
    kwargs.update(overrides)
    return WeighmentRecord(**kwargs)  # type: ignore[arg-type]


class TestComputeWeighmentResult:
    def test_no_underweight_cylinders_is_a_pass(self) -> None:
        assert compute_weighment_result(0) == "pass"

    def test_any_underweight_cylinder_is_a_fail(self) -> None:
        assert compute_weighment_result(1) == "fail"
        assert compute_weighment_result(5) == "fail"


class TestConstruction:
    def test_rejects_an_unknown_context(self) -> None:
        with pytest.raises(InvariantViolation, match="Unknown weighment context"):
            _record(context="something_else")

    def test_rejects_an_unknown_reference_type(self) -> None:
        with pytest.raises(InvariantViolation, match="Unknown weighment reference type"):
            _record(reference_type="order")

    def test_rejects_an_unknown_result(self) -> None:
        with pytest.raises(InvariantViolation, match="Unknown weighment result"):
            _record(result="maybe")

    def test_rejects_a_zero_or_negative_batch_total(self) -> None:
        with pytest.raises(InvariantViolation, match="batch must be positive"):
            _record(total_cylinders_in_batch=0)

    def test_rejects_checked_greater_than_total(self) -> None:
        with pytest.raises(InvariantViolation, match="at most the batch total"):
            _record(total_cylinders_in_batch=10, cylinders_checked=11)

    def test_rejects_a_zero_checked_count(self) -> None:
        with pytest.raises(InvariantViolation, match="must be positive"):
            _record(cylinders_checked=0)

    def test_rejects_a_negative_underweight_count(self) -> None:
        with pytest.raises(InvariantViolation, match="cannot be negative"):
            _record(underweight_cylinder_count=-1)

    def test_rejects_underweight_count_exceeding_checked(self) -> None:
        with pytest.raises(InvariantViolation, match="cannot exceed the number checked"):
            _record(cylinders_checked=5, underweight_cylinder_count=6)

    def test_a_goods_receipt_sample_may_check_less_than_the_full_batch(self) -> None:
        # 10% sampling — this is the whole point of the context.
        record = _record(
            context="goods_receipt_sample", total_cylinders_in_batch=100, cylinders_checked=10
        )
        assert record.cylinders_checked == 10

    def test_a_load_out_full_check_must_cover_the_entire_batch(self) -> None:
        with pytest.raises(InvariantViolation, match="must cover every cylinder"):
            _record(
                context="load_out_full_check",
                reference_type="route",
                total_cylinders_in_batch=50,
                cylinders_checked=40,
            )

    def test_a_load_out_full_check_covering_the_whole_batch_is_valid(self) -> None:
        record = _record(
            context="load_out_full_check",
            reference_type="route",
            total_cylinders_in_batch=50,
            cylinders_checked=50,
        )
        assert record.cylinders_checked == record.total_cylinders_in_batch
