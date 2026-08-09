"""``RateLimiter``, against real Redis."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from lpg.application.common.errors import RateLimitExceededError
from lpg.infrastructure.rate_limit.limiter import RateLimiter
from lpg.infrastructure.redis.client import RedisClient

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration


@pytest.fixture
async def limiter(
    integration_settings: Settings, redis_available: bool
) -> AsyncIterator[RateLimiter]:
    if not redis_available:
        pytest.skip("Redis is not reachable — start it with ./scripts/dev-up.sh")
    client = RedisClient(integration_settings)
    client.connect()
    try:
        yield RateLimiter(client)
    finally:
        await client.disconnect()


def _key() -> str:
    return f"tenant:{uuid.uuid4()}:ratelimit:test"


class TestCheck:
    async def test_allows_requests_within_the_limit(self, limiter: RateLimiter) -> None:
        key = _key()

        for expected_remaining in (4, 3, 2, 1, 0):
            result = await limiter.check(key=key, limit=5, window_seconds=60)
            assert result.allowed is True
            assert result.remaining == expected_remaining

    async def test_denies_requests_over_the_limit(self, limiter: RateLimiter) -> None:
        key = _key()
        for _ in range(3):
            await limiter.check(key=key, limit=3, window_seconds=60)

        result = await limiter.check(key=key, limit=3, window_seconds=60)

        assert result.allowed is False
        assert result.remaining == 0
        assert result.retry_after_seconds > 0

    async def test_different_keys_have_independent_counters(self, limiter: RateLimiter) -> None:
        key_a = _key()
        key_b = _key()

        for _ in range(3):
            await limiter.check(key=key_a, limit=3, window_seconds=60)

        result_b = await limiter.check(key=key_b, limit=3, window_seconds=60)
        assert result_b.allowed is True
        assert result_b.remaining == 2

    async def test_window_resets_the_counter(self, limiter: RateLimiter) -> None:
        import asyncio

        key = _key()
        for _ in range(2):
            await limiter.check(key=key, limit=2, window_seconds=1)

        denied = await limiter.check(key=key, limit=2, window_seconds=1)
        assert denied.allowed is False

        await asyncio.sleep(1.2)

        result = await limiter.check(key=key, limit=2, window_seconds=1)
        assert result.allowed is True
        assert result.remaining == 1


class TestEnforce:
    async def test_returns_the_result_when_within_limit(self, limiter: RateLimiter) -> None:
        key = _key()

        result = await limiter.enforce(key=key, limit=5, window_seconds=60)

        assert result.allowed is True

    async def test_raises_when_over_limit(self, limiter: RateLimiter) -> None:
        key = _key()
        for _ in range(2):
            await limiter.enforce(key=key, limit=2, window_seconds=60)

        with pytest.raises(RateLimitExceededError) as exc_info:
            await limiter.enforce(key=key, limit=2, window_seconds=60)

        assert exc_info.value.http_status == 429
        assert exc_info.value.retry_after_seconds > 0
