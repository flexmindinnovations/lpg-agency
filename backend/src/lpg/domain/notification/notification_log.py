"""Notification Log aggregate root."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from lpg.domain.common.base import AggregateRoot, InvariantViolation

_VALID_STATUSES = frozenset({"queued", "sent", "delivered", "failed", "retrying", "dead_lettered"})


class NotificationLog(AggregateRoot):
    """Tracks one outbound send attempt."""

    __slots__ = (
        "_body",
        "_channel",
        "_created_at",
        "_last_error",
        "_notification_type",
        "_recipient_address",
        "_recipient_user_id",
        "_reference_id",
        "_reference_type",
        "_retry_count",
        "_status",
        "_subject",
        "_tenant_id",
        "_updated_at",
    )

    def __init__(
        self,
        *,
        id: uuid.UUID,
        tenant_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
        notification_type: str,
        channel: str,
        recipient_address: str | None,
        subject: str | None,
        body: str,
        status: str = "queued",
        reference_type: str | None = None,
        reference_id: uuid.UUID | None = None,
        retry_count: int = 0,
        last_error: str | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(id, version=version)
        self._tenant_id = tenant_id
        self._recipient_user_id = recipient_user_id
        self._notification_type = notification_type
        self._channel = channel
        self._recipient_address = recipient_address
        self._subject = subject
        self._body = body

        if status not in _VALID_STATUSES:
            msg = f"Invalid status: {status}"
            raise InvariantViolation(msg)
        self._status = status

        self._reference_type = reference_type
        self._reference_id = reference_id
        self._retry_count = retry_count
        self._last_error = last_error

        now = datetime.now(UTC)
        self._created_at = created_at or now
        self._updated_at = updated_at or now

    @classmethod
    def create(
        cls,
        *,
        tenant_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
        notification_type: str,
        channel: str,
        recipient_address: str | None,
        subject: str | None,
        body: str,
        reference_type: str | None = None,
        reference_id: uuid.UUID | None = None,
    ) -> NotificationLog:
        return cls(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            recipient_user_id=recipient_user_id,
            notification_type=notification_type,
            channel=channel,
            recipient_address=recipient_address,
            subject=subject,
            body=body,
            status="queued",
            reference_type=reference_type,
            reference_id=reference_id,
        )

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._tenant_id

    @property
    def recipient_user_id(self) -> uuid.UUID:
        return self._recipient_user_id

    @property
    def notification_type(self) -> str:
        return self._notification_type

    @property
    def channel(self) -> str:
        return self._channel

    @property
    def recipient_address(self) -> str | None:
        return self._recipient_address

    @property
    def subject(self) -> str | None:
        return self._subject

    @property
    def body(self) -> str:
        return self._body

    @property
    def status(self) -> str:
        return self._status

    @property
    def reference_type(self) -> str | None:
        return self._reference_type

    @property
    def reference_id(self) -> uuid.UUID | None:
        return self._reference_id

    @property
    def retry_count(self) -> int:
        return self._retry_count

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    def _update_status(self, new_status: str, error: str | None = None) -> None:
        self._status = new_status
        if error is not None:
            self._last_error = error
        self._updated_at = datetime.now(UTC)

    def mark_sent(self) -> None:
        self._update_status("sent")

    def mark_failed(self, error: str) -> None:
        self._update_status("failed", error=error)

    def mark_retrying(self) -> None:
        self._retry_count += 1
        self._update_status("retrying")

    def mark_dead_lettered(self, error: str | None = None) -> None:
        self._update_status("dead_lettered", error=error)

    def mark_delivered(self) -> None:
        self._update_status("delivered")
