"""Notification Repositories implementation."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import func, select, update

from lpg.domain.notification.in_app_notification import InAppNotification
from lpg.domain.notification.notification_log import NotificationLog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class SqlAlchemyInAppNotificationRepository:
    """SQLAlchemy implementation of InAppNotificationRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, notification: InAppNotification) -> None:
        """Add a new in-app notification."""
        # Using raw SQL for the aggregate save to avoid complex mapping setup,
        # or we could use Core. We'll use SQLAlchemy Core.
        from sqlalchemy import text
        stmt = text("""
            INSERT INTO notification.in_app_notification (
                id, tenant_id, recipient_user_id, notification_type, title, body,
                reference_type, reference_id, is_read, created_at
            ) VALUES (
                :id, :tenant_id, :recipient_user_id, :notification_type, :title, :body,
                :reference_type, :reference_id, :is_read, :created_at
            )
        """)
        await self._session.execute(
            stmt,
            {
                "id": notification.id,
                "tenant_id": notification.tenant_id,
                "recipient_user_id": notification.recipient_user_id,
                "notification_type": notification.notification_type,
                "title": notification.title,
                "body": notification.body,
                "reference_type": notification.reference_type,
                "reference_id": notification.reference_id,
                "is_read": notification.is_read,
                "created_at": notification.created_at,
            },
        )

    async def get_by_id(self, notification_id: uuid.UUID) -> InAppNotification | None:
        """Get an in-app notification by ID."""
        from sqlalchemy import text
        stmt = text("""
            SELECT id, tenant_id, recipient_user_id, notification_type, title, body,
                   reference_type, reference_id, is_read, created_at
            FROM notification.in_app_notification
            WHERE id = :id
        """)
        result = await self._session.execute(stmt, {"id": notification_id})
        row = result.mappings().first()
        if not row:
            return None
        return InAppNotification(
            id=row["id"],
            tenant_id=row["tenant_id"],
            recipient_user_id=row["recipient_user_id"],
            notification_type=row["notification_type"],
            title=row["title"],
            body=row["body"],
            reference_type=row["reference_type"],
            reference_id=row["reference_id"],
            is_read=row["is_read"],
            created_at=row["created_at"],
            version=1,
        )

    async def list_for_user(
        self, user_id: uuid.UUID, skip: int, limit: int, unread_only: bool = False
    ) -> list[InAppNotification]:
        """List notifications for a specific user."""
        from sqlalchemy import text
        query = """
            SELECT id, tenant_id, recipient_user_id, notification_type, title, body,
                   reference_type, reference_id, is_read, created_at
            FROM notification.in_app_notification
            WHERE recipient_user_id = :user_id
        """
        if unread_only:
            query += " AND is_read = false"
        query += " ORDER BY created_at DESC OFFSET :skip LIMIT :limit"
        
        stmt = text(query)
        result = await self._session.execute(stmt, {"user_id": user_id, "skip": skip, "limit": limit})
        notifications = []
        for row in result.mappings():
            notifications.append(
                InAppNotification(
                    id=row["id"],
                    tenant_id=row["tenant_id"],
                    recipient_user_id=row["recipient_user_id"],
                    notification_type=row["notification_type"],
                    title=row["title"],
                    body=row["body"],
                    reference_type=row["reference_type"],
                    reference_id=row["reference_id"],
                    is_read=row["is_read"],
                    created_at=row["created_at"],
                    version=1,
                )
            )
        return notifications

    async def count_unread(self, user_id: uuid.UUID) -> int:
        """Count unread notifications for a specific user."""
        from sqlalchemy import text
        stmt = text("""
            SELECT count(*)
            FROM notification.in_app_notification
            WHERE recipient_user_id = :user_id AND is_read = false
        """)
        result = await self._session.execute(stmt, {"user_id": user_id})
        return result.scalar_one()

    async def save(self, notification: InAppNotification) -> None:
        """Save modifications to an existing notification."""
        from sqlalchemy import text
        stmt = text("""
            UPDATE notification.in_app_notification
            SET is_read = :is_read
            WHERE id = :id
        """)
        await self._session.execute(
            stmt,
            {
                "id": notification.id,
                "is_read": notification.is_read,
            },
        )

    async def mark_all_read(self, user_id: uuid.UUID) -> None:
        """Helper method to mark all as read efficiently."""
        from sqlalchemy import text
        stmt = text("""
            UPDATE notification.in_app_notification
            SET is_read = true
            WHERE recipient_user_id = :user_id AND is_read = false
        """)
        await self._session.execute(stmt, {"user_id": user_id})


class SqlAlchemyNotificationLogRepository:
    """SQLAlchemy implementation of NotificationLogRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, log: NotificationLog) -> None:
        """Add a new notification log."""
        from sqlalchemy import text
        stmt = text("""
            INSERT INTO notification.notification_log (
                id, tenant_id, recipient_user_id, notification_type, channel,
                recipient_address, subject, body, status, reference_type,
                reference_id, retry_count, last_error, created_at, updated_at
            ) VALUES (
                :id, :tenant_id, :recipient_user_id, :notification_type, :channel,
                :recipient_address, :subject, :body, :status, :reference_type,
                :reference_id, :retry_count, :last_error, :created_at, :updated_at
            )
        """)
        await self._session.execute(
            stmt,
            {
                "id": log.id,
                "tenant_id": log.tenant_id,
                "recipient_user_id": log.recipient_user_id,
                "notification_type": log.notification_type,
                "channel": log.channel,
                "recipient_address": log.recipient_address,
                "subject": log.subject,
                "body": log.body,
                "status": log.status,
                "reference_type": log.reference_type,
                "reference_id": log.reference_id,
                "retry_count": log.retry_count,
                "last_error": log.last_error,
                "created_at": log.created_at,
                "updated_at": log.updated_at,
            },
        )

    async def save(self, log: NotificationLog) -> None:
        """Save modifications to an existing notification log."""
        from sqlalchemy import text
        stmt = text("""
            UPDATE notification.notification_log
            SET status = :status,
                retry_count = :retry_count,
                last_error = :last_error,
                updated_at = :updated_at
            WHERE id = :id
        """)
        await self._session.execute(
            stmt,
            {
                "id": log.id,
                "status": log.status,
                "retry_count": log.retry_count,
                "last_error": log.last_error,
                "updated_at": log.updated_at,
            },
        )
