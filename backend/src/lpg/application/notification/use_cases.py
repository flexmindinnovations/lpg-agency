"""Notification use cases."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lpg.application.common.errors import NotFoundError
from lpg.config.logging import get_logger

if TYPE_CHECKING:
    import uuid

    from lpg.application.common.ports import RealtimePublisher, UnitOfWork
    from lpg.application.notification.ports import (
        DeviceTokenRepository,
        InAppNotificationRepository,
    )
    from lpg.domain.notification.in_app_notification import InAppNotification


class ListNotificationsUseCase:
    def __init__(self, repository: InAppNotificationRepository) -> None:
        self._repository = repository

    async def execute(
        self, user_id: uuid.UUID, skip: int, limit: int, unread_only: bool = False
    ) -> list[InAppNotification]:
        return await self._repository.list_for_user(
            user_id, skip=skip, limit=limit, unread_only=unread_only
        )


class CountUnreadUseCase:
    def __init__(self, repository: InAppNotificationRepository) -> None:
        self._repository = repository

    async def execute(self, user_id: uuid.UUID) -> int:
        return await self._repository.count_unread(user_id)


_logger = get_logger(__name__)


async def _publish_best_effort(
    publisher: RealtimePublisher | None, channel: str, message: dict[str, str]
) -> None:
    """Realtime is an enhancement (ADR-015): the read is already committed,
    and a Redis hiccup must not turn it into an error — other tabs catch up
    on their next fetch."""
    if publisher is None:
        return
    try:
        await publisher.publish(channel, message)
    except Exception:  # noqa: BLE001 - best-effort, logged
        _logger.warning("notification_read_publish_failed", message_type=message.get("type"))


def user_channel(tenant_id: uuid.UUID, user_id: uuid.UUID) -> str:
    """The per-user realtime channel (the `notifications` intent)."""
    return f"tenant:{tenant_id}:user:{user_id}"


class MarkReadUseCase:
    """Marks one notification read, then tells the user's other tabs and
    devices (after commit) so their badge and inbox follow."""

    def __init__(
        self,
        uow: UnitOfWork,
        repository: InAppNotificationRepository,
        publisher: RealtimePublisher | None = None,
    ) -> None:
        self._uow = uow
        self._repository = repository
        self._publisher = publisher

    async def execute(self, notification_id: uuid.UUID, user_id: uuid.UUID) -> None:
        async with self._uow:
            notification = await self._repository.get_by_id(notification_id)
            if not notification or notification.recipient_user_id != user_id:
                raise NotFoundError("Notification not found")

            notification.mark_read()
            await self._repository.save(notification)
            await self._uow.commit()

        await _publish_best_effort(
            self._publisher,
            user_channel(notification.tenant_id, user_id),
            {"type": "notification.read", "notification_id": str(notification_id)},
        )


class MarkAllReadUseCase:
    def __init__(
        self,
        uow: UnitOfWork,
        repository: InAppNotificationRepository,
        publisher: RealtimePublisher | None = None,
    ) -> None:
        self._uow = uow
        self._repository = repository
        self._publisher = publisher

    async def execute(self, user_id: uuid.UUID, tenant_id: uuid.UUID | None = None) -> None:
        async with self._uow:
            await self._repository.mark_all_read(user_id)
            await self._uow.commit()

        if tenant_id is not None:
            await _publish_best_effort(
                self._publisher, user_channel(tenant_id, user_id), {"type": "notification.read_all"}
            )


class RegisterDeviceUseCase:
    """Register (or refresh) an FCM token for the current user's device."""

    def __init__(self, uow: UnitOfWork, repository: DeviceTokenRepository) -> None:
        self._uow = uow
        self._repository = repository

    async def execute(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        token: str,
        platform: str,
    ) -> None:
        from lpg.domain.notification.device_token import DeviceToken

        async with self._uow:
            await self._repository.upsert(
                DeviceToken(
                    tenant_id=tenant_id,
                    recipient_user_id=user_id,
                    token=token.strip(),
                    platform=platform,
                )
            )


class UnregisterDeviceUseCase:
    """Drop a token — on logout, or when the app is told the token is stale."""

    def __init__(self, uow: UnitOfWork, repository: DeviceTokenRepository) -> None:
        self._uow = uow
        self._repository = repository

    async def execute(self, *, token: str) -> None:
        async with self._uow:
            await self._repository.delete_by_token(token.strip())
