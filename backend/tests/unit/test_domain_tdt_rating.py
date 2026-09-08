"""Unit tests for the TDT (Targeted Delivery Time) star rating domain
module (Phase 20 subsystem 2). Every band/fine number here is a
TEST FIXTURE — not a real MDG figure, confirm before go-live."""

from __future__ import annotations

from decimal import Decimal

import pytest

from lpg.domain.common.base import InvariantViolation
from lpg.domain.compliance.tdt_rating import (
    TdtBandDistributionEntry,
    TdtFineRule,
    TdtStarBand,
    compute_fine_percent,
    compute_quarterly_rating,
    compute_star_for_order,
)

# TEST FIXTURE bands — not real MDG figures, confirm before go-live.
_BANDS = (
    TdtStarBand(stars=5, max_days=1),
    TdtStarBand(stars=4, max_days=2),
    TdtStarBand(stars=3, max_days=4),
    TdtStarBand(stars=2, max_days=7),
    TdtStarBand(stars=1, max_days=None),
)


class TestComputeStarForOrder:
    def test_same_day_delivery_hits_the_top_band(self) -> None:
        assert compute_star_for_order(0, _BANDS) == 5

    def test_exact_boundary_day_count_hits_that_band(self) -> None:
        assert compute_star_for_order(1, _BANDS) == 5
        assert compute_star_for_order(2, _BANDS) == 4

    def test_a_day_past_a_boundary_drops_to_the_next_band(self) -> None:
        assert compute_star_for_order(3, _BANDS) == 3

    def test_anything_beyond_the_last_finite_band_hits_the_catch_all(self) -> None:
        assert compute_star_for_order(8, _BANDS) == 1
        assert compute_star_for_order(1000, _BANDS) == 1

    def test_rejects_a_negative_day_count(self) -> None:
        with pytest.raises(InvariantViolation, match="cannot be negative"):
            compute_star_for_order(-1, _BANDS)

    def test_rejects_empty_bands(self) -> None:
        with pytest.raises(InvariantViolation, match="cannot be empty"):
            compute_star_for_order(1, ())

    def test_rejects_a_stars_value_outside_1_to_5(self) -> None:
        bands = (TdtStarBand(stars=6, max_days=None),)
        with pytest.raises(InvariantViolation, match="between 1 and 5"):
            compute_star_for_order(1, bands)

    def test_rejects_a_non_terminal_unbounded_band(self) -> None:
        bands = (
            TdtStarBand(stars=5, max_days=None),
            TdtStarBand(stars=1, max_days=10),
        )
        with pytest.raises(InvariantViolation, match="Only the last"):
            compute_star_for_order(1, bands)

    def test_rejects_a_non_positive_max_days(self) -> None:
        bands = (
            TdtStarBand(stars=5, max_days=0),
            TdtStarBand(stars=1, max_days=None),
        )
        with pytest.raises(InvariantViolation, match="must be positive"):
            compute_star_for_order(1, bands)

    def test_rejects_bands_missing_the_catch_all(self) -> None:
        bands = (TdtStarBand(stars=5, max_days=5),)
        with pytest.raises(InvariantViolation, match="catch-all"):
            compute_star_for_order(1, bands)

    def test_rejects_bands_not_sorted_ascending(self) -> None:
        bands = (
            TdtStarBand(stars=5, max_days=5),
            TdtStarBand(stars=4, max_days=2),
            TdtStarBand(stars=1, max_days=None),
        )
        with pytest.raises(InvariantViolation, match="sorted ascending"):
            compute_star_for_order(1, bands)


class TestComputeQuarterlyRating:
    def test_an_empty_period_has_no_rating(self) -> None:
        rating = compute_quarterly_rating((), _BANDS)
        assert rating.overall_stars is None
        assert rating.total_orders == 0
        assert rating.distribution == ()

    def test_a_single_order_rating_equals_its_own_band(self) -> None:
        rating = compute_quarterly_rating((1,), _BANDS)
        assert rating.overall_stars == 5
        assert rating.total_orders == 1
        assert rating.distribution == (TdtBandDistributionEntry(stars=5, order_count=1),)

    def test_mixed_orders_produce_a_rounded_mean_and_full_distribution(self) -> None:
        # 5, 5, 1 -> mean 3.67 -> rounds to 4
        rating = compute_quarterly_rating((1, 1, 100), _BANDS)
        assert rating.overall_stars == 4
        assert rating.total_orders == 3
        counts = {entry.stars: entry.order_count for entry in rating.distribution}
        assert counts == {5: 2, 1: 1}

    def test_a_uniform_top_rated_quarter_stays_at_the_top_band(self) -> None:
        rating = compute_quarterly_rating((1, 1), _BANDS)
        assert rating.overall_stars == 5


class TestComputeFinePercent:
    # TEST FIXTURE schedule — not real MDG figures, confirm before go-live.
    _SCHEDULE = (
        TdtFineRule(consecutive_low_quarters=2, fine_percent=Decimal("1.5")),
        TdtFineRule(consecutive_low_quarters=4, fine_percent=Decimal("3.0")),
    )

    def test_no_streak_owes_no_fine(self) -> None:
        assert compute_fine_percent(0, self._SCHEDULE) == Decimal("0")

    def test_a_streak_below_any_threshold_owes_no_fine(self) -> None:
        assert compute_fine_percent(1, self._SCHEDULE) == Decimal("0")

    def test_meeting_a_threshold_applies_its_fine(self) -> None:
        assert compute_fine_percent(2, self._SCHEDULE) == Decimal("1.5")
        assert compute_fine_percent(3, self._SCHEDULE) == Decimal("1.5")

    def test_meeting_a_higher_threshold_applies_the_higher_fine(self) -> None:
        assert compute_fine_percent(4, self._SCHEDULE) == Decimal("3.0")
        assert compute_fine_percent(10, self._SCHEDULE) == Decimal("3.0")

    def test_an_empty_schedule_owes_no_fine(self) -> None:
        assert compute_fine_percent(10, ()) == Decimal("0")

    def test_rejects_a_negative_streak(self) -> None:
        with pytest.raises(InvariantViolation, match="cannot be negative"):
            compute_fine_percent(-1, self._SCHEDULE)
