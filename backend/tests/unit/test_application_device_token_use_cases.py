"""Unit tests for the device-token use cases."""

import uuid

import pytest

from lpg.application.notification.use_cases import (
    RegisterDeviceUseCase,
    UnregisterDeviceUseCase,
)
from lpg.domain.notification.device_token import DeviceToken


class FakeUnitOfWork:
    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_: object) -> None:
        pass


class FakeDeviceTokenRepository:
    def __init__(self) -> None:
        self.by_token: dict[str, DeviceToken] = {}

    async def upsert(self, token: DeviceToken) -> None:
        self.by_token[token.token] = token

    async def delete_by_token(self, token: str) -> None:
        self.by_token.pop(token, None)

    async def list_for_user(self, user_id: uuid.UUID) -> list[DeviceToken]:
        return [t for t in self.by_token.values() if t.recipient_user_id == user_id]


@pytest.fixture
def repo() -> FakeDeviceTokenRepository:
    return FakeDeviceTokenRepository()


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.mark.asyncio
async def test_register_stores_a_trimmed_token(
    repo: FakeDeviceTokenRepository, uow: FakeUnitOfWork
) -> None:
    tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
    await RegisterDeviceUseCase(uow, repo).execute(
        tenant_id=tenant_id,
        user_id=user_id,
        token="  tok-1  ",
        platform="android",
    )
    assert "tok-1" in repo.by_token
    stored = repo.by_token["tok-1"]
    assert stored.recipient_user_id == user_id
    assert stored.tenant_id == tenant_id


@pytest.mark.asyncio
async def test_register_is_idempotent_per_token(
    repo: FakeDeviceTokenRepository, uow: FakeUnitOfWork
) -> None:
    user_a, user_b = uuid.uuid4(), uuid.uuid4()
    tenant = uuid.uuid4()
    for user in (user_a, user_b):
        await RegisterDeviceUseCase(uow, repo).execute(
            tenant_id=tenant, user_id=user, token="shared", platform="ios"
        )
    # Token reassigned to whoever registered last — not duplicated.
    assert len(repo.by_token) == 1
    assert repo.by_token["shared"].recipient_user_id == user_b


@pytest.mark.asyncio
async def test_unregister_removes_the_token(
    repo: FakeDeviceTokenRepository, uow: FakeUnitOfWork
) -> None:
    await RegisterDeviceUseCase(uow, repo).execute(
        tenant_id=uuid.uuid4(), user_id=uuid.uuid4(), token="bye", platform="web"
    )
    await UnregisterDeviceUseCase(uow, repo).execute(token="bye")
    assert repo.by_token == {}


@pytest.mark.asyncio
async def test_unregister_unknown_token_is_a_noop(
    repo: FakeDeviceTokenRepository, uow: FakeUnitOfWork
) -> None:
    await UnregisterDeviceUseCase(uow, repo).execute(token="never-seen")
    assert repo.by_token == {}
