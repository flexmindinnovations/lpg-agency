"""Redis connection foundation, against a real Redis.

Phase 1 verifies the connection and its lifecycle only. Caching, the job
queue and the real-time Pub/Sub backplane are later phases — Redis is
foundation infrastructure here, nothing more.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from lpg.config.settings import Settings
from lpg.infrastructure.redis.client import RedisClient

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.integration


@pytest.fixture
async def redis_client(
    integration_settings: Settings, redis_available: bool
) -> AsyncIterator[RedisClient]:
    if not redis_available:
        pytest.skip("Redis is not reachable — start it with ./scripts/dev-up.sh")
    client = RedisClient(integration_settings)
    client.connect()
    try:
        yield client
    finally:
        await client.disconnect()


class TestConnection:
    async def test_ping_succeeds(self, redis_client: RedisClient) -> None:
        assert await redis_client.ping() is True

    async def test_set_and_get_round_trip(self, redis_client: RedisClient) -> None:
        key = f"lpg:test:{uuid.uuid4().hex}"
        await redis_client.client.set(key, "value", ex=30)
        try:
            assert await redis_client.client.get(key) == "value"
        finally:
            await redis_client.client.delete(key)

    async def test_expiry_is_honoured(self, redis_client: RedisClient) -> None:
        """TTL support is a prerequisite for the cache and idempotency store."""
        key = f"lpg:test:{uuid.uuid4().hex}"
        await redis_client.client.set(key, "value", ex=30)
        try:
            ttl = await redis_client.client.ttl(key)
            assert 0 < ttl <= 30
        finally:
            await redis_client.client.delete(key)


class TestLifecycle:
    async def test_accessing_the_client_before_connect_raises(
        self, integration_settings: Settings
    ) -> None:
        """Failing loudly beats returning a silently unusable client."""
        client = RedisClient(integration_settings)
        with pytest.raises(RuntimeError, match="connect"):
            _ = client.client

    async def test_disconnect_is_idempotent(self, integration_settings: Settings) -> None:
        """Shutdown paths run more than once. This must not be the thing that
        turns a graceful stop into a crash."""
        client = RedisClient(integration_settings)
        client.connect()
        await client.disconnect()
        await client.disconnect()

    async def test_ping_reports_false_when_unreachable(self) -> None:
        """Readiness reports; it never raises.

        A readiness probe that throws produces a 500 instead of a 503, and the
        platform cannot tell "unhealthy" from "broken".
        """
        settings = Settings(
            environment="local",
            redis_url="redis://127.0.0.1:1/0",  # nothing listens on port 1
        )
        client = RedisClient(settings)
        client.connect()
        try:
            assert await client.ping() is False
        finally:
            await client.disconnect()
