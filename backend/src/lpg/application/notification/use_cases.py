"""Notification use cases."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lpg.application.common.errors import NotFoundError

if TYPE_CHECKING:
    import uuid

    from lpg.application.common.ports import UnitOfWork
    from lpg.application.notification.ports import InAppNotificationRepository
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


class MarkReadUseCase:
    def __init__(self, uow: UnitOfWork, repository: InAppNotificationRepository) -> None:
        self._uow = uow
        self._repository = repository

    async def execute(self, notification_id: uuid.UUID, user_id: uuid.UUID) -> None:
        async with self._uow:
            notification = await self._repository.get_by_id(notification_id)
            if not notification or notification.recipient_user_id != user_id:
                raise NotFoundError("Notification not found")

            notification.mark_read()
            await self._repository.save(notification)


class MarkAllReadUseCase:
    def __init__(self, uow: UnitOfWork, repository: InAppNotificationRepository) -> None:
        self._uow = uow
        self._repository = repository

    async def execute(self, user_id: uuid.UUID) -> None:
        async with self._uow:
            await self._repository.mark_all_read(user_id)
