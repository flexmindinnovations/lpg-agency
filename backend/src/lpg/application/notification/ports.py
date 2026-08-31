"""Notification application ports."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid

    from lpg.domain.notification.device_token import DeviceToken
    from lpg.domain.notification.in_app_notification import InAppNotification
    from lpg.domain.notification.notification_log import NotificationLog


class InAppNotificationRepository(Protocol):
    """Port for InAppNotification persistence."""

    async def add(self, notification: InAppNotification) -> None:
        """Add a new in-app notification."""
        ...

    async def get_by_id(self, notification_id: uuid.UUID) -> InAppNotification | None:
        """Get an in-app notification by ID."""
        ...

    async def list_for_user(
        self, user_id: uuid.UUID, skip: int, limit: int, unread_only: bool = False
    ) -> list[InAppNotification]:
        """List notifications for a specific user."""
        ...

    async def count_unread(self, user_id: uuid.UUID) -> int:
        """Count unread notifications for a specific user."""
        ...

    async def save(self, notification: InAppNotification) -> None:
        """Save modifications to an existing notification."""
        ...

    async def mark_all_read(self, user_id: uuid.UUID) -> None:
        """Mark all notifications as read for a specific user."""
        ...


class NotificationLogRepository(Protocol):
    """Port for NotificationLog persistence."""

    async def add(self, log: NotificationLog) -> None:
        """Add a new notification log."""
        ...

    async def save(self, log: NotificationLog) -> None:
        """Save modifications to an existing notification log."""
        ...


class EmailChannel(Protocol):
    """Port for sending email notifications."""

    async def send(self, *, to: str, subject: str, body: str) -> None:
        """Send an email."""
        ...


class SmsChannel(Protocol):
    """Port for sending SMS notifications."""

    async def send(self, *, to: str, body: str) -> None:
        """Send an SMS."""
        ...


class DeviceTokenRepository(Protocol):
    """Port for DeviceToken persistence."""

    async def upsert(self, token: DeviceToken) -> None:
        """Register a token, or refresh `last_seen_at` (and reassign the
        owning user) if this exact token string already exists."""
        ...

    async def delete_by_token(self, token: str) -> None:
        """Remove a token — called on logout / when FCM reports it stale."""
        ...

    async def list_for_user(self, user_id: uuid.UUID) -> list[DeviceToken]:
        """Every registered token for a user, across their devices."""
        ...


class PushChannel(Protocol):
    """Port for sending a push notification to one device token."""

    async def send(
        self,
        *,
        token: str,
        platform: str,
        title: str,
        body: str,
        data: dict[str, str],
    ) -> None:
        """Deliver to a single device. Raises on a hard failure; raises
        `PushTokenInvalidError` specifically when the provider reports the
        token is permanently unregistered so the caller can prune it."""
        ...


class PushTokenInvalidError(Exception):
    """The push provider rejected the token as permanently invalid."""

    def __init__(self, token: str) -> None:
        super().__init__(f"Push token no longer valid: ...{token[-8:]}")
        self.token = token


class BranchStaffResolver(Protocol):
    """Resolves the identity user IDs for staff eligible to receive branch notifications."""

    async def resolve_for_branch(
        self,
        tenant_id: uuid.UUID,
        branch_id: uuid.UUID,
        eligible_roles: frozenset[str],
    ) -> list[uuid.UUID]:
        """Returns a list of identity user_ids."""
        ...
