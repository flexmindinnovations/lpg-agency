"""Unit tests for notification use cases."""

import uuid

import pytest

from lpg.application.common.errors import NotFoundError
from lpg.application.notification.use_cases import (
    CountUnreadUseCase,
    MarkReadUseCase,
)
from lpg.domain.notification.in_app_notification import InAppNotification


class FakeUnitOfWork:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class FakeInAppNotificationRepository:
    def __init__(self) -> None:
        self.notifications: dict[uuid.UUID, InAppNotification] = {}

    async def add(self, notification: InAppNotification) -> None:
        self.notifications[notification.id] = notification

    async def save(self, notification: InAppNotification) -> None:
        pass

    async def get_by_id(self, notification_id: uuid.UUID) -> InAppNotification | None:
        return self.notifications.get(notification_id)

    async def list_for_user(
        self, user_id: uuid.UUID, *, skip: int = 0, limit: int = 50, unread_only: bool = False
    ) -> list[InAppNotification]:
        results = [n for n in self.notifications.values() if n.recipient_user_id == user_id]
        if unread_only:
            results = [n for n in results if not n.is_read]
        # Sort by created_at desc (in memory mock, we just return the list)
        return results[skip : skip + limit]

    async def count_unread(self, user_id: uuid.UUID) -> int:
        return sum(
            1
            for n in self.notifications.values()
            if n.recipient_user_id == user_id and not n.is_read
        )

    async def mark_all_read(self, user_id: uuid.UUID) -> None:
        for n in self.notifications.values():
            if n.recipient_user_id == user_id and not n.is_read:
                n.mark_read()


@pytest.fixture
def repo() -> FakeInAppNotificationRepository:
    return FakeInAppNotificationRepository()


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.mark.asyncio
async def test_count_unread_use_case(repo: FakeInAppNotificationRepository) -> None:
    user_id = uuid.uuid4()
    n1 = InAppNotification.create(
        tenant_id=uuid.uuid4(),
        recipient_user_id=user_id,
        notification_type="booking_confirmed",
        title="Test",
        body="Body",
        reference_type=None,
        reference_id=None,
    )
    await repo.add(n1)

    use_case = CountUnreadUseCase(repo)
    assert await use_case.execute(user_id) == 1

    n1.mark_read()
    assert await use_case.execute(user_id) == 0


@pytest.mark.asyncio
async def test_mark_read_use_case(
    repo: FakeInAppNotificationRepository, uow: FakeUnitOfWork
) -> None:
    user_id = uuid.uuid4()
    n1 = InAppNotification.create(
        tenant_id=uuid.uuid4(),
        recipient_user_id=user_id,
        notification_type="booking_confirmed",
        title="Test",
        body="Body",
        reference_type=None,
        reference_id=None,
    )
    await repo.add(n1)

    use_case = MarkReadUseCase(uow, repo)
    await use_case.execute(n1.id, user_id)

    assert n1.is_read


@pytest.mark.asyncio
async def test_mark_read_rejects_wrong_user(
    repo: FakeInAppNotificationRepository, uow: FakeUnitOfWork
) -> None:
    user_id = uuid.uuid4()
    n1 = InAppNotification.create(
        tenant_id=uuid.uuid4(),
        recipient_user_id=user_id,
        notification_type="booking_confirmed",
        title="Test",
        body="Body",
        reference_type=None,
        reference_id=None,
    )
    await repo.add(n1)

    use_case = MarkReadUseCase(uow, repo)
    with pytest.raises(NotFoundError):
        await use_case.execute(n1.id, uuid.uuid4())
