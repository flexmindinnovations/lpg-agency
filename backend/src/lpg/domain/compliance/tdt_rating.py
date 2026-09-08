"""Targeted Delivery Time (TDT) star rating — Regulatory & MDG Compliance
Phase 20 subsystem 2 (`planning/features/20-regulatory-compliance/PLAN.md`
§2). The OMC's quarterly delivery-turnaround metric: booking date →
delivery date, banded into a 5★-to-1★ rating per order, with a fine
schedule that scales on repeat sub-threshold quarters.

Every number this module operates on — star-band day-thresholds, fine
percentages — comes from tenant-configured, MDG-edition-stamped reference
data (`TenantConfiguration` keys `tdt_star_rating_bands`/`tdt_fine_
schedule`), **never a constant in this file**. The source plan is explicit
that the applicable MDG edition (2022 vs. an unconfirmed 2024 revision) is
still an open question — hardcoding a threshold here would bake in a guess
this codebase has no way to verify.

Same shape as `weighment_record.py`: free functions holding the actual
domain logic (not methods on a class), specifically so a future MDG edition
with a different banding rule, aggregation formula, or fine schedule is a
one-function change, not a redesign. Two of these functions
(`_aggregate_overall_stars`, the fine-schedule threshold rule in
`compute_fine_percent`) are themselves *unconfirmed* against the actual MDG
clause text — see each docstring — and are named/isolated for exactly that
reason.

Frozen dataclasses throughout, no I/O — unit-testable without a database,
same as every other pure domain module in this codebase.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from lpg.domain.common.base import InvariantViolation

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True, slots=True)
class TdtStarBand:
    """One row of tenant-configured, MDG-edition-stamped reference data —
    never a hardcoded constant. `max_days` is inclusive: an order with
    `days_to_deliver <= max_days` qualifies for `stars`. Bands must be
    supplied sorted ascending by `max_days`, and the last band must have
    `max_days=None` (the unbounded catch-all covering every day-count the
    faster bands didn't) — `compute_star_for_order` validates this shape
    on every call rather than trusting the caller.
    """

    stars: int
    max_days: int | None


@dataclass(frozen=True, slots=True)
class TdtFineRule:
    """One row of a tenant-configured fine schedule — MDG's own wording is
    "fines scaling on repeat," modelled here as a threshold: a distributor
    with at least `consecutive_low_quarters` back-to-back sub-threshold
    quarters owes `fine_percent`. Never a hardcoded constant."""

    consecutive_low_quarters: int
    fine_percent: Decimal


@dataclass(frozen=True, slots=True)
class TdtBandDistributionEntry:
    stars: int
    order_count: int


@dataclass(frozen=True, slots=True)
class TdtQuarterlyRating:
    """`overall_stars` is `None` specifically for a quarter/branch with zero
    delivered orders in the period — there is no rating to publish, and
    silently defaulting to a specific star value would misrepresent that as
    a real (good or bad) outcome rather than "no data yet."
    """

    overall_stars: int | None
    total_orders: int
    distribution: tuple[TdtBandDistributionEntry, ...]


def _validate_bands(bands: Sequence[TdtStarBand]) -> None:
    if not bands:
        msg = "TDT star bands cannot be empty."
        raise InvariantViolation(msg)
    for band in bands:
        if not (1 <= band.stars <= 5):
            msg = f"TDT star band 'stars' must be between 1 and 5, got {band.stars}."
            raise InvariantViolation(msg)
    for index, band in enumerate(bands):
        is_last = index == len(bands) - 1
        if band.max_days is None and not is_last:
            msg = "Only the last TDT star band may have max_days=None (the unbounded catch-all)."
            raise InvariantViolation(msg)
        if band.max_days is not None and band.max_days <= 0:
            msg = f"TDT star band 'max_days' must be positive, got {band.max_days}."
            raise InvariantViolation(msg)
    if bands[-1].max_days is not None:
        msg = "TDT star bands must end with a max_days=None catch-all band."
        raise InvariantViolation(msg)
    finite_days = [band.max_days for band in bands if band.max_days is not None]
    if finite_days != sorted(finite_days):
        msg = "TDT star bands must be sorted ascending by max_days."
        raise InvariantViolation(msg)


def compute_star_for_order(days_to_deliver: int, bands: Sequence[TdtStarBand]) -> int:
    """Bands a single order's booking-to-delivery day-count into a star
    value against tenant-configured, MDG-edition-stamped thresholds. Free
    function so a future MDG edition changing the day-thresholds is a
    tenant-configuration change (no code change at all), and a future
    edition changing the *banding rule itself* is this one function, not a
    class redesign — matching `compute_weighment_result`'s documented
    reasoning exactly.
    """
    if days_to_deliver < 0:
        msg = f"Days to deliver cannot be negative, got {days_to_deliver}."
        raise InvariantViolation(msg)
    _validate_bands(bands)
    for band in bands:
        if band.max_days is None or days_to_deliver <= band.max_days:
            return band.stars
    # Unreachable: _validate_bands guarantees the last band is an
    # unbounded (max_days=None) catch-all, so the loop above always
    # returns before falling through.
    msg = "No TDT star band matched; bands must end with an unbounded catch-all."
    raise InvariantViolation(msg)


def _aggregate_overall_stars(per_order_stars: Sequence[int]) -> int:
    """UNCONFIRMED against the actual MDG clause text (`planning/features/
    20-regulatory-compliance/PLAN.md`'s own open-questions list) — the
    source plan states each *order* gets a 5-to-1 star rating but never
    specifies how a *quarter's* single published rating aggregates them
    (arithmetic mean? a percentile threshold, e.g. "X% of orders must hit
    5★"? something else?). Defaults to the simple arithmetic mean, rounded
    to the nearest star and clamped to the valid 1-5 range — a reasonable
    placeholder, not a confirmed regulatory formula. Isolated as its own
    function specifically so swapping in whatever the real clause specifies
    is a one-function change, the same reasoning `compute_weighment_result`
    and `compute_star_for_order` already document for their own rules.
    """
    mean = sum(per_order_stars) / len(per_order_stars)
    return min(5, max(1, round(mean)))


def compute_quarterly_rating(
    order_days: Sequence[int], bands: Sequence[TdtStarBand]
) -> TdtQuarterlyRating:
    """Bands every delivered order's day-count in the period and rolls them
    up into one quarterly (or live in-quarter) rating. `order_days` is
    empty for a branch/period with no delivered orders yet — this returns
    `overall_stars=None` rather than guessing, see `TdtQuarterlyRating`.
    """
    if not order_days:
        return TdtQuarterlyRating(overall_stars=None, total_orders=0, distribution=())
    per_order_stars = [compute_star_for_order(days, bands) for days in order_days]
    counts: dict[int, int] = {}
    for stars in per_order_stars:
        counts[stars] = counts.get(stars, 0) + 1
    distribution = tuple(
        TdtBandDistributionEntry(stars=stars, order_count=counts[stars])
        for stars in sorted(counts, reverse=True)
    )
    return TdtQuarterlyRating(
        overall_stars=_aggregate_overall_stars(per_order_stars),
        total_orders=len(order_days),
        distribution=distribution,
    )


def compute_fine_percent(consecutive_low_quarters: int, schedule: Sequence[TdtFineRule]) -> Decimal:
    """MDG's own wording is "fines scaling on repeat" — modelled as a
    threshold schedule: the highest-tier rule whose
    `consecutive_low_quarters` requirement is met applies. A tenant with no
    fine rules configured, or a streak that doesn't yet meet any
    configured threshold, owes no fine (`Decimal("0")`) — this function
    never invents a percentage the tenant didn't configure. Free function
    for the same reason `compute_weighment_result` and
    `compute_star_for_order` are: a future MDG edition changing the
    scaling rule (e.g. per-star-band fines instead of a flat repeat-count
    schedule) is a one-function change, not a redesign.

    UNCONFIRMED against the actual MDG clause text which quarters count as
    "low" for this streak in the first place (e.g. below a specific star
    floor, or any quarter that triggered a fine) — that determination
    happens by the caller before this function is reached; this function
    only maps an already-computed streak length to a percentage.
    """
    if consecutive_low_quarters < 0:
        msg = f"Consecutive low-quarter count cannot be negative, got {consecutive_low_quarters}."
        raise InvariantViolation(msg)
    applicable = [
        rule for rule in schedule if rule.consecutive_low_quarters <= consecutive_low_quarters
    ]
    if not applicable:
        return Decimal("0")
    return max(applicable, key=lambda rule: rule.consecutive_low_quarters).fine_percent
