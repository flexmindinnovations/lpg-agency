"""`FeatureFlag`/`FeatureFlagOverride`/`FeatureFlagService` — no database
required.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from lpg.domain.common.base import InvariantViolation
from lpg.domain.platform.feature_flag import FeatureFlag, FeatureFlagOverride, FeatureFlagService

_TENANT_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
_TENANT_B = uuid.UUID("22222222-2222-2222-2222-222222222222")


class TestFeatureFlagConstruction:
    def test_rejects_a_rollout_percentage_above_100(self) -> None:
        with pytest.raises(InvariantViolation):
            FeatureFlag("new_ui", "New UI", rollout_percentage=101)

    def test_rejects_a_negative_rollout_percentage(self) -> None:
        with pytest.raises(InvariantViolation):
            FeatureFlag("new_ui", "New UI", rollout_percentage=-1)

    def test_rejects_a_start_time_at_or_after_the_end_time(self) -> None:
        now = datetime.now(UTC)
        with pytest.raises(InvariantViolation):
            FeatureFlag("new_ui", "New UI", starts_at=now, ends_at=now)


class TestFeatureFlagMutation:
    def test_set_rollout_percentage_rejects_out_of_range(self) -> None:
        flag = FeatureFlag("new_ui", "New UI")

        with pytest.raises(InvariantViolation):
            flag.set_rollout_percentage(150)

    def test_schedule_rejects_start_after_end(self) -> None:
        flag = FeatureFlag("new_ui", "New UI")
        now = datetime.now(UTC)

        with pytest.raises(InvariantViolation):
            flag.schedule(starts_at=now + timedelta(days=1), ends_at=now)


class TestFeatureFlagService:
    def test_an_unknown_flag_is_always_off(self) -> None:
        result = FeatureFlagService.is_enabled(None, None, _TENANT_A, at=datetime.now(UTC))

        assert result is False

    def test_off_by_default_with_no_override_is_off(self) -> None:
        flag = FeatureFlag("new_ui", "New UI", is_enabled_by_default=False)

        result = FeatureFlagService.is_enabled(flag, None, _TENANT_A, at=datetime.now(UTC))

        assert result is False

    def test_on_by_default_with_no_override_and_no_rollout_cap_is_on(self) -> None:
        flag = FeatureFlag("new_ui", "New UI", is_enabled_by_default=True)

        result = FeatureFlagService.is_enabled(flag, None, _TENANT_A, at=datetime.now(UTC))

        assert result is True

    def test_a_tenant_override_enabling_wins_even_when_the_default_is_off(self) -> None:
        flag = FeatureFlag("new_ui", "New UI", is_enabled_by_default=False)
        override = FeatureFlagOverride(uuid.uuid4(), _TENANT_A, "new_ui", is_enabled=True)

        result = FeatureFlagService.is_enabled(flag, override, _TENANT_A, at=datetime.now(UTC))

        assert result is True

    def test_a_tenant_override_disabling_wins_even_when_the_default_is_on(self) -> None:
        flag = FeatureFlag("new_ui", "New UI", is_enabled_by_default=True)
        override = FeatureFlagOverride(uuid.uuid4(), _TENANT_A, "new_ui", is_enabled=False)

        result = FeatureFlagService.is_enabled(flag, override, _TENANT_A, at=datetime.now(UTC))

        assert result is False

    def test_before_the_scheduled_start_the_flag_is_off_even_with_an_enabling_override(
        self,
    ) -> None:
        now = datetime.now(UTC)
        flag = FeatureFlag(
            "new_ui", "New UI", is_enabled_by_default=True, starts_at=now + timedelta(days=1)
        )

        result = FeatureFlagService.is_enabled(flag, None, _TENANT_A, at=now)

        assert result is False

    def test_after_the_scheduled_end_the_flag_is_off(self) -> None:
        now = datetime.now(UTC)
        flag = FeatureFlag(
            "new_ui", "New UI", is_enabled_by_default=True, ends_at=now - timedelta(days=1)
        )

        result = FeatureFlagService.is_enabled(flag, None, _TENANT_A, at=now)

        assert result is False

    def test_a_zero_percent_rollout_with_no_override_is_off(self) -> None:
        flag = FeatureFlag("new_ui", "New UI", is_enabled_by_default=True, rollout_percentage=0)

        result = FeatureFlagService.is_enabled(flag, None, _TENANT_A, at=datetime.now(UTC))

        assert result is False

    def test_a_hundred_percent_rollout_is_on_for_any_tenant(self) -> None:
        flag = FeatureFlag("new_ui", "New UI", is_enabled_by_default=True, rollout_percentage=100)

        assert FeatureFlagService.is_enabled(flag, None, _TENANT_A, at=datetime.now(UTC)) is True
        assert FeatureFlagService.is_enabled(flag, None, _TENANT_B, at=datetime.now(UTC)) is True

    def test_rollout_bucketing_is_stable_for_the_same_tenant_across_calls(self) -> None:
        flag = FeatureFlag("new_ui", "New UI", is_enabled_by_default=True, rollout_percentage=50)
        now = datetime.now(UTC)

        first = FeatureFlagService.is_enabled(flag, None, _TENANT_A, at=now)
        second = FeatureFlagService.is_enabled(flag, None, _TENANT_A, at=now)

        assert first == second

    def test_rollout_bucketing_differs_by_tenant_at_a_fixed_percentage(self) -> None:
        # Precomputed: sha256("11111...1")%100 == 37 (< 50, included);
        # sha256("22222...2")%100 == 95 (>= 50, excluded). A deterministic
        # boundary check, not a statistical/flaky one.
        flag = FeatureFlag("new_ui", "New UI", is_enabled_by_default=True, rollout_percentage=50)
        now = datetime.now(UTC)

        assert FeatureFlagService.is_enabled(flag, None, _TENANT_A, at=now) is True
        assert FeatureFlagService.is_enabled(flag, None, _TENANT_B, at=now) is False
