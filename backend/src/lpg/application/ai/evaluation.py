"""The evaluation harness — AI Operational Intelligence, Horizon 1 Stage 1c.

`22-ai-operational-intelligence/PLAN.md`'s cross-cutting rule: *"a model
that cannot beat 'same interval as last time' ships nothing"*, and
*"backtest on held-out time periods, never random splits — random splits
leak the future into training and every model looks excellent."*

This module does the scoring half only. Producing the observations is each
heuristic's own job and needs its point-in-time features (Stage 1a) — the
caller must construct each `Observation` at an `as_of` date using *only*
data that existed then, and pair it with what actually happened afterward.
The harness aggregates candidate-vs-baseline error and reports whether the
candidate wins; a caller (a `tests/evaluation/` case) asserts on
`beats_baseline` so a losing heuristic fails CI rather than shipping on a
hunch.

Deliberately tiny for Horizon 1 — there is no real history to backtest
against yet. The value is that the seam exists, so Stage 2's refill
heuristic has a measured baseline from day one and every Horizon-2 model
is compared here on the same terms.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid
    from collections.abc import Iterable, Sequence
    from datetime import date


@dataclass(frozen=True, slots=True)
class Observation:
    """One backtest point. `predicted` is what the candidate would have
    said at `as_of` (seeing only data up to then); `baseline` is what the
    named naive rule would have said for the same point; `actual` is what
    happened. All three are the same unit (days, cylinders, minutes, ...)."""

    subject_id: uuid.UUID
    as_of: date
    predicted: float
    baseline: float
    actual: float


def absolute_errors(pairs: Iterable[tuple[float, float]]) -> list[float]:
    """`|predicted - actual|` for each `(predicted, actual)` pair."""
    return [abs(predicted - actual) for predicted, actual in pairs]


def mean_absolute_error(pairs: Iterable[tuple[float, float]]) -> float:
    errs = absolute_errors(pairs)
    return sum(errs) / len(errs) if errs else 0.0


def mean_absolute_percentage_error(pairs: Iterable[tuple[float, float]]) -> float | None:
    """`mean(|predicted - actual| / |actual|)`, as a fraction. `None` when
    any `actual` is 0 — MAPE is undefined there and silently dropping those
    points would flatter the score."""
    ratios: list[float] = []
    for predicted, actual in pairs:
        if actual == 0:
            return None
        ratios.append(abs(predicted - actual) / abs(actual))
    return sum(ratios) / len(ratios) if ratios else 0.0


@dataclass(frozen=True, slots=True)
class BacktestReport:
    n: int
    baseline_name: str
    candidate_mae: float
    baseline_mae: float
    candidate_mape: float | None
    baseline_mape: float | None

    @property
    def beats_baseline(self) -> bool:
        """Strictly lower mean absolute error than the baseline, on a
        non-empty sample. A tie does not count as a win — matching the
        plan's "cannot beat ... ships nothing"."""
        return self.n > 0 and self.candidate_mae < self.baseline_mae

    @property
    def mae_improvement(self) -> float:
        """Fraction of the baseline's error the candidate removes
        (negative = worse). `0.0` when there's nothing to compare."""
        if self.n == 0 or self.baseline_mae == 0:
            return 0.0
        return (self.baseline_mae - self.candidate_mae) / self.baseline_mae


def backtest(observations: Sequence[Observation], *, baseline_name: str) -> BacktestReport:
    """Score a candidate against its named baseline over point-in-time
    observations. Time-split is a property of how the caller built the
    observations (each at its own `as_of`, using only prior data), not
    something this function enforces — it cannot see the training set."""
    candidate_pairs = [(o.predicted, o.actual) for o in observations]
    baseline_pairs = [(o.baseline, o.actual) for o in observations]
    return BacktestReport(
        n=len(observations),
        baseline_name=baseline_name,
        candidate_mae=mean_absolute_error(candidate_pairs),
        baseline_mae=mean_absolute_error(baseline_pairs),
        candidate_mape=mean_absolute_percentage_error(candidate_pairs),
        baseline_mape=mean_absolute_percentage_error(baseline_pairs),
    )
