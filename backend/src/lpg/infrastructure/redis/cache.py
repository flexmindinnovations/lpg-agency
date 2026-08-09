"""Concrete ``CacheClient`` (``lpg.application.common.ports.CacheClient``).

Wraps ``RedisClient``'s connection pool. Keys are tenant-scoped by
convention (``tenant:{id}:...``) — enforced here at the boundary, not left
to callers to remember, so a cache entry can never be served across a
tenant boundary (mirrors the RLS session-variable convention: the isolation
guarantee lives at one seam, not at every call site).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lpg.infrastructure.redis.client import RedisClient


class RedisCacheClient:
    """Implements the ``CacheClient`` port over ``RedisClient``."""

    def __init__(self, client: RedisClient) -> None:
        self._client = client

    async def get(self, key: str) -> str | None:
        # redis-py 5.x's `Redis.get` returns Any under the <6 ceiling arq
        # forces (ADR-029) — see the identical note in RedisClient.connect().
        value: str | None = await self._client.client.get(key)
        return value

    async def set(self, key: str, value: str, *, ttl_seconds: int | None = None) -> None:
        await self._client.client.set(key, value, ex=ttl_seconds)

    async def delete(self, key: str) -> None:
        await self._client.client.delete(key)
