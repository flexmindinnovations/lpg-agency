"""Unit tests for staff reminders: message wording and the rate limit."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from lpg.application.common.errors import RateLimitExceededError, ValidationError
from lpg.application.order.reminders import (
    MAX_PER_DAY,
    OrderReminder,
    check_rate_limit,
    compose_message,
)
from lpg.infrastructure.notification.catalog import spec_for

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)


def _sent(minutes_ago: int) -> OrderReminder:
    return OrderReminder(
        id=uuid.uuid4(),
        order_id=uuid.uuid4(),
        sent_by=uuid.uuid4(),
        preset="custom",
        message="hi",
        sent_at=NOW - timedelta(minutes=minutes_ago),
    )


def test_preset_names_the_order_and_the_driver() -> None:
    text = compose_message("on_the_way", None, order_ref="ORD000033", driver_name="Ravi Kumar")
    assert text == ("ORD000033 is on its way with Ravi. Please keep your delivery code ready.")


def test_custom_text_is_trimmed_and_required() -> None:
    assert compose_message("custom", "  Please  call us ", order_ref="O", driver_name=None) == (
        "Please call us"
    )
    with pytest.raises(ValidationError):
        compose_message("custom", "   ", order_ref="O", driver_name=None)
    with pytest.raises(ValidationError):
        compose_message("custom", "x" * 301, order_ref="O", driver_name=None)


def test_unknown_preset_is_refused() -> None:
    with pytest.raises(ValidationError):
        compose_message("nope", None, order_ref="O", driver_name=None)


def test_second_reminder_within_two_minutes_is_limited() -> None:
    with pytest.raises(RateLimitExceededError):
        check_rate_limit([_sent(1)], NOW)
    check_rate_limit([_sent(3)], NOW)


def test_daily_cap() -> None:
    history = [_sent(10 * (i + 1)) for i in range(MAX_PER_DAY)]
    with pytest.raises(RateLimitExceededError):
        check_rate_limit(history, NOW)
    check_rate_limit([_sent(60 * 25)] * MAX_PER_DAY, NOW)


def test_notification_body_is_the_message() -> None:
    spec = spec_for("order_reminder")
    assert spec is not None
    assert spec.body({"message": "Hello"}) == "Hello"
    assert spec.push is True


def test_driver_presets_are_separate_from_customer_ones() -> None:
    text = compose_message(
        "driver_hurry", None, order_ref="ORD000033", driver_name=None, audience="driver"
    )
    assert "ORD000033" in text
    with pytest.raises(ValidationError):
        compose_message("driver_hurry", None, order_ref="O", driver_name=None)
    with pytest.raises(ValidationError):
        compose_message("on_the_way", None, order_ref="O", driver_name=None, audience="driver")


def test_rate_limit_counts_each_audience_on_its_own() -> None:
    driver_sent = _sent(1)
    object.__setattr__(driver_sent, "preset", "driver_hurry")
    check_rate_limit([driver_sent], NOW, "customer")
    with pytest.raises(RateLimitExceededError):
        check_rate_limit([driver_sent], NOW, "driver")


def test_driver_notification_goes_to_the_driver_with_push() -> None:
    spec = spec_for("order_reminder_driver")
    assert spec is not None
    assert spec.body({"message": "Hello"}) == "Hello"
    assert spec.push is True
