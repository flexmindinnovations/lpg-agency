"""Redis connection foundation.

Redis serves five distinct roles in this platform — cache, sessions, rate
limiting, the background-job queue, and the real-time Pub/Sub backplane
(ADR-015). That concentration is deliberate (it avoids a second managed
service) but it makes Redis a critical dependency, so it is monitored as one
and its failure must degrade features rather than break core operations.

Phase 1 provides the connection and a health check. Cache, queue and publisher
implementations arrive with the phases that need them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import redis.asyncio as redis

from lpg.config.logging import get_logger

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from lpg.config.settings import Settings

_logger = get_logger(__name__)


class RedisClient:
    """Owns the Redis connection pool for the process lifetime."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Redis | None = None

    @property
    def client(self) -> Redis:
        if self._client is None:
            msg = "RedisClient.connect() has not been called"
            raise RuntimeError(msg)
        return self._client

    def connect(self) -> None:
        """Create the connection pool. Does not open a connection."""
        self._client = redis.from_url(
            str(self._settings.redis_url),
            encoding="utf-8",
            decode_responses=True,
            health_check_interval=30,
        )
        _logger.info("redis_client_created")

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            _logger.info("redis_client_closed")

    async def ping(self) -> bool:
        """Return whether Redis is reachable. Used by readiness."""
        try:
            await self.client.ping()
        except Exception as exc:  # noqa: BLE001 - readiness reports, never raises
            _logger.warning("redis_ping_failed", error=str(exc))
            return False
        return True


def build_redis_client(settings: Settings | None = None) -> RedisClient:
    """Construct a RedisClient from settings."""
    from lpg.config.settings import get_settings

    return RedisClient(settings or get_settings())
