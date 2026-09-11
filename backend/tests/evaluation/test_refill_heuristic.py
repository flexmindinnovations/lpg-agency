"""Backtest for the refill-due heuristic (AI Operational Intelligence,
Horizon 1 Stage 2) against its named baseline, "same interval as last
time" — i.e. predicting the next gap equals the customer's own last
observed gap, unshrunk. Synthetic delivery histories, no DB: each history
is walked with a trailing window so every observation uses only data that
existed *before* the date being predicted (never the future gap itself),
the harness's own "never a random split" rule
(`application/ai/evaluation.py`).
"""

from __future__ import annotations

import random
import uuid
from datetime import date, timedelta

from lpg.application.ai.evaluation import Observation, backtest
from lpg.application.customer.refill_prediction import (
    MIN_DELIVERIES_FOR_OWN_INTERVAL,
    compute_shrunk_interval,
)

_BASELINE_NAME = "same interval as last time"


def _synthetic_delivery_gaps(
    rng: random.Random, *, true_interval: float, count: int, noise: float
) -> list[float]:
    """`count` delivery gaps scattered around `true_interval` — a
    customer whose real cadence is fixed but each individual gap wobbles,
    the realistic case a rolling mean/shrinkage is meant to smooth out."""
    return [max(1.0, rng.gauss(true_interval, noise)) for _ in range(count)]


def _walk_customer(
    rng: random.Random,
    *,
    customer_true_interval: float,
    gaps: list[float],
    population_mean: float,
) -> list[Observation]:
    """Walks one customer's delivery history date-by-date, predicting each
    gap from only the gaps *before* it — candidate = `compute_shrunk_
    interval` using the customer's own trailing mean + delivery count so
    far; baseline = the single most recent gap, unshrunk. `actual` is the
    gap that really happened next (drawn independently, same distribution
    — the ground truth this run's history didn't get to see)."""
    subject_id = uuid.uuid4()
    as_of = date(2026, 1, 1)
    observations: list[Observation] = []

    for i in range(1, len(gaps)):
        seen = gaps[:i]
        own_avg = sum(seen) / len(seen)
        candidate = compute_shrunk_interval(
            own_avg_interval_days=own_avg,
            own_delivery_count=len(seen),
            population_mean_interval_days=population_mean,
        )
        baseline = seen[-1]
        actual = rng.gauss(customer_true_interval, 3.0)
        assert candidate is not None
        observations.append(
            Observation(
                subject_id=subject_id,
                as_of=as_of + timedelta(days=i),
                predicted=candidate,
                baseline=baseline,
                actual=max(1.0, actual),
            )
        )
    return observations


def test_shrunk_interval_beats_same_interval_as_last_time_for_sparse_customers() -> None:
    """The heuristic's whole reason to shrink is sparse/noisy customers
    (< MIN_DELIVERIES_FOR_OWN_INTERVAL) — this is exactly where "just use
    the last gap" is most exposed to a single fluke, so it's the case the
    plan's "cannot beat ... ships nothing" rule must hold for."""
    rng = random.Random(42)  # noqa: S311 - test fixture data, not crypto
    population_mean = 25.0  # the tenant-wide average interval, in days

    observations: list[Observation] = []
    for _ in range(30):
        true_interval = rng.uniform(18.0, 32.0)
        gaps = _synthetic_delivery_gaps(
            rng,
            true_interval=true_interval,
            count=MIN_DELIVERIES_FOR_OWN_INTERVAL,  # sparse: never reaches full trust
            noise=8.0,  # a noisy customer -- the case shrinkage exists for
        )
        observations.extend(
            _walk_customer(
                rng,
                customer_true_interval=true_interval,
                gaps=gaps,
                population_mean=population_mean,
            )
        )

    report = backtest(observations, baseline_name=_BASELINE_NAME)

    assert report.n > 0
    assert report.beats_baseline, (
        f"shrunk interval (MAE={report.candidate_mae:.2f}) did not beat "
        f"'{_BASELINE_NAME}' (MAE={report.baseline_mae:.2f})"
    )
