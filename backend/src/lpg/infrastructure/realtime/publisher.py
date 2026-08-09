"""Concrete ``RealtimePublisher`` (``lpg.application.common.ports.RealtimePublisher``).

Wraps ``RedisClient``'s connection pool with a plain ``PUBLISH`` — Redis
Pub/Sub is fire-and-forget with no persistence and no delivery guarantee,
which is the deliberate trade-off ADR-015 makes (real-time is an
enhancement, never the source of truth; see `16-realtime-architecture.md`
§6). This module is only the publish side. The WebSocket connection
manager and per-subscription RBAC authorization (`16-realtime-architecture.md`
§3, §5) are Phase 6+ scope — they need real Authentication to authorize a
subscription the same way a REST `GET` is authorized, which does not exist
yet.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lpg.infrastructure.redis.client import RedisClient


class RedisRealtimePublisher:
    """Implements the ``RealtimePublisher`` port over ``RedisClient``."""

    def __init__(self, client: RedisClient) -> None:
        self._client = client

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        # json.dumps, not the message dict directly — Redis PUBLISH carries
        # bytes/str payloads, never structured objects.
        await self._client.client.publish(channel, json.dumps(message))
