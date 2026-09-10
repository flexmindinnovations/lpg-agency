"""Tests for the evaluation harness itself (`application/ai/evaluation.py`).

The per-heuristic backtests (refill interval, demand, ...) land alongside
this file as Stages 2-5 ship; this one just proves the scoring is honest —
a better candidate wins, a worse one is flagged, ties do not count.
"""

from __future__ import annotations

import uuid
from datetime import date

from lpg.application.ai.evaluation import (
    Observation,
    backtest,
    mean_absolute_error,
    mean_absolute_percentage_error,
)


def _obs(predicted: float, baseline: float, actual: float) -> Observation:
    return Observation(
        subject_id=uuid.uuid4(),
        as_of=date(2026, 1, 1),
        predicted=predicted,
        baseline=baseline,
        actual=actual,
    )


def test_mae_and_mape_basic() -> None:
    assert mean_absolute_error([(10.0, 8.0), (5.0, 5.0)]) == 1.0
    assert mean_absolute_percentage_error([(10.0, 8.0)]) == 0.25


def test_mape_is_none_when_an_actual_is_zero() -> None:
    assert mean_absolute_percentage_error([(1.0, 0.0)]) is None


def test_empty_sample_is_not_a_win() -> None:
    report = backtest([], baseline_name="same interval as last time")
    assert report.n == 0
    assert report.beats_baseline is False
    assert report.mae_improvement == 0.0


def test_a_better_candidate_beats_its_baseline() -> None:
    # Candidate is spot on; baseline is off by 5 days each time.
    observations = [_obs(predicted=30.0, baseline=25.0, actual=30.0) for _ in range(4)]
    report = backtest(observations, baseline_name="trailing-28d mean")

    assert report.n == 4
    assert report.candidate_mae == 0.0
    assert report.baseline_mae == 5.0
    assert report.beats_baseline is True
    assert report.mae_improvement == 1.0


def test_a_worse_candidate_is_flagged_not_shipped() -> None:
    # Candidate is off by 10, baseline by 2.
    observations = [_obs(predicted=40.0, baseline=32.0, actual=30.0) for _ in range(3)]
    report = backtest(observations, baseline_name="same interval as last time")

    assert report.candidate_mae == 10.0
    assert report.baseline_mae == 2.0
    assert report.beats_baseline is False
    assert report.mae_improvement < 0


def test_a_tie_does_not_count_as_a_win() -> None:
    observations = [_obs(predicted=28.0, baseline=32.0, actual=30.0) for _ in range(2)]
    report = backtest(observations, baseline_name="trailing-28d mean")
    assert report.candidate_mae == report.baseline_mae == 2.0
    assert report.beats_baseline is False
