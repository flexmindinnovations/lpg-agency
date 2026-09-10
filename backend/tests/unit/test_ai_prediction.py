"""Unit tests for `RecordPredictionUseCase` and `hash_inputs`
(AI Operational Intelligence — Horizon 1, Stage 1). Fake repository, no DB.
"""

from __future__ import annotations

import uuid

import pytest

from lpg.application.ai.prediction import (
    Prediction,
    RecordPredictionCommand,
    RecordPredictionUseCase,
    hash_inputs,
)


class _FakePredictionRepository:
    def __init__(self) -> None:
        self.added: list[Prediction] = []
        self._next = uuid.uuid4()

    def next_id(self) -> uuid.UUID:
        return self._next

    async def add(self, prediction: Prediction) -> None:
        self.added.append(prediction)

    async def latest_for_subject(
        self, *, prediction_type: str, subject_id: uuid.UUID
    ) -> Prediction | None:
        matches = [
            p
            for p in self.added
            if p.prediction_type == prediction_type and p.subject_id == subject_id
        ]
        return matches[-1] if matches else None


@pytest.mark.asyncio
async def test_records_a_prediction_with_the_supplied_fields() -> None:
    repo = _FakePredictionRepository()
    tenant_id = uuid.uuid4()
    subject_id = uuid.uuid4()

    returned_id = await RecordPredictionUseCase(repo).execute(
        RecordPredictionCommand(
            tenant_id=tenant_id,
            prediction_type="refill_due",
            subject_type="customer",
            subject_id=subject_id,
            model_version="refill_heuristic_v1",
            value={"refill_due_date": "2026-10-01"},
            inputs={"last_delivered_at": "2026-09-01", "interval_days": 30},
        )
    )

    assert returned_id == repo.next_id()
    assert len(repo.added) == 1
    recorded = repo.added[0]
    assert recorded.tenant_id == tenant_id
    assert recorded.subject_id == subject_id
    assert recorded.prediction_type == "refill_due"
    assert recorded.model_version == "refill_heuristic_v1"
    assert recorded.value == {"refill_due_date": "2026-10-01"}
    assert recorded.input_hash is not None and len(recorded.input_hash) == 64


@pytest.mark.asyncio
async def test_input_hash_is_none_when_no_inputs_given() -> None:
    repo = _FakePredictionRepository()
    await RecordPredictionUseCase(repo).execute(
        RecordPredictionCommand(
            tenant_id=uuid.uuid4(),
            prediction_type="reorder_signal",
            subject_type="inventory_location",
            subject_id=uuid.uuid4(),
            model_version="reorder_v1",
            value={"shortfall": 12},
        )
    )
    assert repo.added[0].input_hash is None


def test_hash_inputs_is_stable_regardless_of_key_order() -> None:
    a = hash_inputs({"b": 2, "a": 1})
    b = hash_inputs({"a": 1, "b": 2})
    assert a == b


def test_hash_inputs_changes_when_a_value_changes() -> None:
    assert hash_inputs({"interval_days": 30}) != hash_inputs({"interval_days": 31})
