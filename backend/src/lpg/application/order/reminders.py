"""Staff reminders to a customer about their order.

A reminder is a short message (one of a few presets, or free text) pushed to
the customer's app. Every one is recorded against the order, which is what
the order page's timeline shows and what the rate limit counts.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Protocol

from lpg.application.common.errors import RateLimitExceededError, ValidationError

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any

#: Between two reminders for the same order, and in any rolling day.
MIN_GAP = timedelta(minutes=2)
MAX_PER_DAY = 5
MAX_CUSTOM_LENGTH = 300

CUSTOM = "custom"

#: Preset key -> (label shown to staff, message sent to the customer).
#: `{order}` is the order number, `{driver}` the driver's first name.
PRESETS: Mapping[str, tuple[str, str]] = {
    "delivery_today": (
        "Delivery today",
        "{order} is planned for delivery today. Please keep someone at the address.",
    ),
    "on_the_way": (
        "On the way",
        "{order} is on its way with {driver}. Please keep your delivery code ready.",
    ),
    "empty_ready": (
        "Keep empty ready",
        "Please keep your empty cylinder ready for {order} so the driver can collect it.",
    ),
    "payment_due": (
        "Payment due",
        "A payment is pending for {order}. You can pay in the app or at the door.",
    ),
}


@dataclass(frozen=True, slots=True)
class OrderReminder:
    id: uuid.UUID
    order_id: uuid.UUID
    sent_by: uuid.UUID
    preset: str
    message: str
    sent_at: datetime


class OrderReminderRepository(Protocol):
    async def add(self, reminder: OrderReminder, tenant_id: uuid.UUID) -> None: ...

    async def list_for_order(self, order_id: uuid.UUID) -> list[OrderReminder]: ...


class Notifier(Protocol):
    async def notify(self, payload: dict[str, Any]) -> None: ...


def compose_message(
    preset: str, custom_text: str | None, *, order_ref: str, driver_name: str | None
) -> str:
    if preset == CUSTOM:
        text = " ".join((custom_text or "").split())
        if not text:
            msg = "Write the message to send."
            raise ValidationError(msg, errors={"message": ["Write the message to send."]})
        if len(text) > MAX_CUSTOM_LENGTH:
            msg = f"Keep the message under {MAX_CUSTOM_LENGTH} characters."
            raise ValidationError(msg, errors={"message": [msg]})
        return text
    found = PRESETS.get(preset)
    if found is None:
        msg = "Choose one of the ready-made messages, or write your own."
        raise ValidationError(msg, errors={"preset": [msg]})
    first_name = (driver_name or "").split(" ")[0] or "our driver"
    return found[1].format(order=order_ref, driver=first_name)


def check_rate_limit(history: list[OrderReminder], now: datetime) -> None:
    if history:
        latest = max(r.sent_at for r in history)
        wait = latest + MIN_GAP - now
        if wait > timedelta(0):
            msg = "A reminder for this order was just sent. Please wait a couple of minutes."
            raise RateLimitExceededError(msg, retry_after_seconds=int(wait.total_seconds()) + 1)
    in_day = [r for r in history if r.sent_at > now - timedelta(days=1)]
    if len(in_day) >= MAX_PER_DAY:
        oldest = min(r.sent_at for r in in_day)
        retry = int((oldest + timedelta(days=1) - now).total_seconds()) + 1
        msg = f"This customer has already had {MAX_PER_DAY} reminders for this order today."
        raise RateLimitExceededError(msg, retry_after_seconds=retry)


def new_reminder(
    *, order_id: uuid.UUID, sent_by: uuid.UUID, preset: str, message: str
) -> OrderReminder:
    return OrderReminder(
        id=uuid.uuid4(),
        order_id=order_id,
        sent_by=sent_by,
        preset=preset,
        message=message,
        sent_at=datetime.now(UTC),
    )
