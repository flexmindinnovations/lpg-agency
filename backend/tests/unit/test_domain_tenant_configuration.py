"""`TenantConfiguration`/`TenantConfigurationResolver` — no database
required.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from lpg.domain.common.base import InvariantViolation
from lpg.domain.tenant.tenant_configuration import TenantConfiguration, TenantConfigurationResolver

_TENANT_ID = uuid.uuid4()


def _entry(config_key: str, value: object, effective_from: datetime) -> TenantConfiguration:
    return TenantConfiguration(uuid.uuid4(), _TENANT_ID, config_key, value, effective_from)


class TestConstruction:
    def test_rejects_an_unrecognized_key(self) -> None:
        with pytest.raises(InvariantViolation):
            TenantConfiguration(uuid.uuid4(), _TENANT_ID, "made_up_key", "5", datetime.now(UTC))

    def test_accepts_every_recognized_key(self) -> None:
        for key in ("gst_rate_percent", "cancellation_fee_amount", "credit_limit_default"):
            TenantConfiguration(uuid.uuid4(), _TENANT_ID, key, "1", datetime.now(UTC))


class TestResolver:
    def test_returns_none_when_no_entry_exists_for_the_key(self) -> None:
        result = TenantConfigurationResolver.resolve([], "gst_rate_percent", datetime.now(UTC))

        assert result is None

    def test_returns_none_when_every_entry_is_in_the_future(self) -> None:
        now = datetime.now(UTC)
        entries = [_entry("gst_rate_percent", "5.0", now + timedelta(days=1))]

        result = TenantConfigurationResolver.resolve(entries, "gst_rate_percent", now)

        assert result is None

    def test_returns_the_single_applicable_entry(self) -> None:
        now = datetime.now(UTC)
        entry = _entry("gst_rate_percent", "5.0", now - timedelta(days=1))

        result = TenantConfigurationResolver.resolve([entry], "gst_rate_percent", now)

        assert result is entry

    def test_returns_the_most_recent_entry_not_later_than_the_query_time(self) -> None:
        now = datetime.now(UTC)
        older = _entry("gst_rate_percent", "5.0", now - timedelta(days=30))
        newer = _entry("gst_rate_percent", "12.0", now - timedelta(days=1))

        result = TenantConfigurationResolver.resolve([older, newer], "gst_rate_percent", now)

        assert result is newer

    def test_a_historical_query_gets_the_value_in_effect_back_then_not_the_latest(self) -> None:
        old_effective = datetime(2026, 1, 1, tzinfo=UTC)
        new_effective = datetime(2026, 6, 1, tzinfo=UTC)
        query_time = datetime(2026, 3, 1, tzinfo=UTC)
        older = _entry("gst_rate_percent", "5.0", old_effective)
        newer = _entry("gst_rate_percent", "12.0", new_effective)

        result = TenantConfigurationResolver.resolve([older, newer], "gst_rate_percent", query_time)

        assert result is older

    def test_ignores_entries_for_a_different_key(self) -> None:
        now = datetime.now(UTC)
        other_key = _entry("cancellation_fee_amount", "50", now - timedelta(days=1))

        result = TenantConfigurationResolver.resolve([other_key], "gst_rate_percent", now)

        assert result is None
