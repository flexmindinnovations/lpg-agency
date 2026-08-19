"""Unit tests for the NotificationLog aggregate root.

Covers `create()`'s initial `queued` state and the `NotificationSent`
domain event (R10) recorded by every `mark_*` status transition.
"""

from __future__ import annotations

import uuid

import pytest

from lpg.domain.common.base import InvariantViolation
from lpg.domain.notification.notification_log import NotificationLog, NotificationSent


def _make_log(**kwargs: object) -> NotificationLog:
    defaults: dict[str, object] = {
        "tenant_id": uuid.uuid4(),
        "recipient_user_id": uuid.uuid4(),
        "notification_type": "booking_confirmed",
        "channel": "email",
        "recipient_address": "customer@example.com",
        "subject": "Order Confirmed",
        "body": "Your order has been confirmed.",
    }
    defaults.update(kwargs)
    return NotificationLog.create(**defaults)  # type: ignore[arg-type]


class TestNotificationLogCreation:
    def test_create_starts_queued(self) -> None:
        log = _make_log()
        assert log.status == "queued"
        assert log.retry_count == 0
        assert log.last_error is None

    def test_create_records_no_event(self) -> None:
        """Unlike `Employee`'s constructor, `create()` itself is not a
        status transition — `NotificationSent` only fires from `mark_*`."""
        log = _make_log()
        assert log.events == ()

    def test_rejects_invalid_status(self) -> None:
        with pytest.raises(InvariantViolation, match="Invalid status"):
            NotificationLog(
                id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                recipient_user_id=uuid.uuid4(),
                notification_type="booking_confirmed",
                channel="email",
                recipient_address=None,
                subject=None,
                body="x",
                status="bogus",
            )


class TestStatusTransitionsRecordNotificationSent:
    def test_mark_sent(self) -> None:
        log = _make_log()
        log.mark_sent()
        assert log.status == "sent"

        events = [e for e in log.events if isinstance(e, NotificationSent)]
        assert len(events) == 1
        event = events[0]
        assert event.notification_id == log.id
        assert event.tenant_id == log.tenant_id
        assert event.recipient_user_id == log.recipient_user_id
        assert event.channel == "email"
        assert event.notification_type == "booking_confirmed"
        assert event.status == "sent"
        assert event.provider_message_id is None

    def test_mark_failed_records_error_and_event(self) -> None:
        log = _make_log()
        log.mark_failed("SMTP timeout")

        assert log.status == "failed"
        assert log.last_error == "SMTP timeout"
        events = [e for e in log.events if isinstance(e, NotificationSent)]
        assert len(events) == 1
        assert events[0].status == "failed"

    def test_mark_retrying_increments_retry_count_and_records_event(self) -> None:
        log = _make_log()
        log.mark_retrying()
        log.mark_retrying()

        assert log.status == "retrying"
        assert log.retry_count == 2
        events = [e for e in log.events if isinstance(e, NotificationSent)]
        assert len(events) == 2
        assert all(e.status == "retrying" for e in events)

    def test_mark_dead_lettered(self) -> None:
        log = _make_log()
        log.mark_dead_lettered("exhausted retries")

        assert log.status == "dead_lettered"
        events = [e for e in log.events if isinstance(e, NotificationSent)]
        assert len(events) == 1
        assert events[0].status == "dead_lettered"

    def test_mark_delivered(self) -> None:
        log = _make_log()
        log.mark_sent()
        log.mark_delivered()

        assert log.status == "delivered"
        events = [e for e in log.events if isinstance(e, NotificationSent)]
        assert len(events) == 2
        assert events[-1].status == "delivered"
