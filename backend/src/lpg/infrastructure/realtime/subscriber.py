"""Redis Pub/Sub subscriber loop (``16-realtime-architecture.md`` §3).

Runs as a background ``asyncio.Task`` for the process lifetime. It subscribes
to ``tenant:*`` via Redis ``PSUBSCRIBE``, and on each message routes the
payload to the ``ConnectionManager`` for fan-out to local WebSocket clients.

Reconnects automatically with exponential backoff if the Redis connection
drops — real-time degrades but core operations are unaffected (§7).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import TYPE_CHECKING, Any

from lpg.config.logging import get_logger

if TYPE_CHECKING:
    from lpg.infrastructure.realtime.connection_manager import ConnectionManager
    from lpg.infrastructure.redis.client import RedisClient

_logger = get_logger(__name__)

# Backoff parameters for reconnection.
_INITIAL_BACKOFF_S = 1.0
_MAX_BACKOFF_S = 30.0
_BACKOFF_FACTOR = 2.0


class RedisSubscriber:
    """Background subscriber that routes Redis Pub/Sub messages to local WebSockets."""

    def __init__(self, redis_client: RedisClient, connection_manager: ConnectionManager) -> None:
        self._redis = redis_client
        self._manager = connection_manager
        self._task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self) -> None:
        """Start the subscriber loop as a background task."""
        if self._task is not None:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        _logger.info("redis_subscriber_started")

    async def stop(self) -> None:
        """Gracefully stop the subscriber loop."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        _logger.info("redis_subscriber_stopped")

    async def _run_loop(self) -> None:
        """Reconnecting subscriber loop with exponential backoff."""
        backoff = _INITIAL_BACKOFF_S

        while self._running:
            try:
                await self._subscribe_and_listen()
                backoff = _INITIAL_BACKOFF_S  # Reset on clean exit
            except asyncio.CancelledError:
                return
            except Exception:
                _logger.exception("redis_subscriber_error")
                if not self._running:
                    return  # type: ignore[unreachable]
                _logger.info("redis_subscriber_reconnecting", backoff_seconds=backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * _BACKOFF_FACTOR, _MAX_BACKOFF_S)

    async def _subscribe_and_listen(self) -> None:
        """Subscribe to tenant:* pattern and process incoming messages."""
        pubsub = self._redis.client.pubsub()
        try:
            await pubsub.psubscribe("tenant:*")
            _logger.info("redis_subscribed", pattern="tenant:*")

            while self._running:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
                if message is None:
                    continue

                if message["type"] == "pmessage":
                    channel: str = message["channel"]
                    try:
                        data: dict[str, Any] = json.loads(message["data"])
                    except (json.JSONDecodeError, TypeError):
                        _logger.warning("redis_message_decode_failed", channel=channel)
                        continue

                    await self._manager.broadcast(channel, data)
        finally:
            await pubsub.punsubscribe("tenant:*")
            await pubsub.aclose()  # type: ignore[no-untyped-call]
