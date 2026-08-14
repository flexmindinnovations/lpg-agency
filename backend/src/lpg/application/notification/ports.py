"""Notification application ports."""

from __future__ import annotations

import uuid
from typing import Protocol

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
