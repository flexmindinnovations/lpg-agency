"""``RedisCacheClient``, against real Redis."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from lpg.infrastructure.redis.cache import RedisCacheClient
from lpg.infrastructure.redis.client import RedisClient

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration


@pytest.fixture
async def cache(
    integration_settings: Settings, redis_available: bool
) -> AsyncIterator[RedisCacheClient]:
    if not redis_available:
        pytest.skip("Redis is not reachable — start it with ./scripts/dev-up.sh")
    client = RedisClient(integration_settings)
    client.connect()
    try:
        yield RedisCacheClient(client)
    finally:
        await client.disconnect()


class TestGetSetDelete:
    async def test_get_returns_none_for_a_missing_key(self, cache: RedisCacheClient) -> None:
        key = f"tenant:{uuid.uuid4()}:missing"

        assert await cache.get(key) is None

    async def test_set_then_get_round_trips(self, cache: RedisCacheClient) -> None:
        key = f"tenant:{uuid.uuid4()}:widget:1"

        await cache.set(key, "cached-value")

        assert await cache.get(key) == "cached-value"

    async def test_delete_removes_the_key(self, cache: RedisCacheClient) -> None:
        key = f"tenant:{uuid.uuid4()}:widget:2"
        await cache.set(key, "value")

        await cache.delete(key)

        assert await cache.get(key) is None

    async def test_ttl_expires_the_key(self, cache: RedisCacheClient) -> None:
        import asyncio

        key = f"tenant:{uuid.uuid4()}:widget:3"

        await cache.set(key, "value", ttl_seconds=1)
        assert await cache.get(key) == "value"

        await asyncio.sleep(1.2)

        assert await cache.get(key) is None

    async def test_no_ttl_persists_beyond_a_short_wait(self, cache: RedisCacheClient) -> None:
        import asyncio

        key = f"tenant:{uuid.uuid4()}:widget:4"

        await cache.set(key, "value")
        await asyncio.sleep(1.2)

        assert await cache.get(key) == "value"
