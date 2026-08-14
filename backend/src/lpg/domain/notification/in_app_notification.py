"""In-App Notification aggregate root."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from lpg.domain.common.base import AggregateRoot, DomainEvent


@dataclass(frozen=True, slots=True)
class InAppNotificationCreated(DomainEvent):
    notification_id: uuid.UUID
    tenant_id: uuid.UUID
    recipient_user_id: uuid.UUID
    notification_type: str
    title: str


class InAppNotification(AggregateRoot):
    """An in-app notification delivered to a specific user."""

    __slots__ = (
        "_body",
        "_created_at",
        "_is_read",
        "_notification_type",
        "_recipient_user_id",
        "_reference_id",
        "_reference_type",
        "_tenant_id",
        "_title",
    )

    def __init__(
        self,
        *,
        id: uuid.UUID,
        tenant_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
        notification_type: str,
        title: str,
        body: str,
        reference_type: str | None = None,
        reference_id: uuid.UUID | None = None,
        is_read: bool = False,
        created_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(id, version=version)
        self._tenant_id = tenant_id
        self._recipient_user_id = recipient_user_id
        self._notification_type = notification_type
        self._title = title
        self._body = body
        self._reference_type = reference_type
        self._reference_id = reference_id
        self._is_read = is_read
        self._created_at = created_at or datetime.now(UTC)

    @classmethod
    def create(
        cls,
        *,
        tenant_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
        notification_type: str,
        title: str,
        body: str,
        reference_type: str | None = None,
        reference_id: uuid.UUID | None = None,
    ) -> InAppNotification:
        notification_id = uuid.uuid4()
        notification = cls(
            id=notification_id,
            tenant_id=tenant_id,
            recipient_user_id=recipient_user_id,
            notification_type=notification_type,
            title=title,
            body=body,
            reference_type=reference_type,
            reference_id=reference_id,
        )
        notification.record_event(
            InAppNotificationCreated(
                notification_id=notification_id,
                tenant_id=tenant_id,
                recipient_user_id=recipient_user_id,
                notification_type=notification_type,
                title=title,
            )
        )
        return notification

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
    def title(self) -> str:
        return self._title

    @property
    def body(self) -> str:
        return self._body

    @property
    def reference_type(self) -> str | None:
        return self._reference_type

    @property
    def reference_id(self) -> uuid.UUID | None:
        return self._reference_id

    @property
    def is_read(self) -> bool:
        return self._is_read

    @property
    def created_at(self) -> datetime:
        return self._created_at

    def mark_read(self) -> None:
        self._is_read = True
