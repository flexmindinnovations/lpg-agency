"""Per-instance WebSocket connection manager (``16-realtime-architecture.md`` §3).

Maintains an in-memory mapping of Redis Pub/Sub channel → set of connected
WebSocket clients. When a message arrives from the Redis subscriber, it is
fanned out to every local connection subscribed to that channel.

Thread-safety is not required: FastAPI's WebSocket handling runs on the
``asyncio`` event loop, and all mutations are performed within coroutines
that yield only at well-defined points.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any, Protocol, runtime_checkable

from lpg.config.logging import get_logger

_logger = get_logger(__name__)


@runtime_checkable
class WebSocket(Protocol):
    """The one method this module actually calls on FastAPI's `WebSocket`.

    A structural `Protocol` instead of importing the real type — this is
    infrastructure, but `16-realtime-architecture.md`'s WebSocket transport
    is itself a FastAPI/Starlette concept, and `ConnectionManager` has no
    reason to know that; it only needs "something with an async
    `send_json`". `fastapi.WebSocket` satisfies this structurally with zero
    coupling in either direction (`FastAPI stays inside the api layer`).
    """

    async def send_json(self, data: Any) -> None: ...


# Backpressure: if a client's send queue exceeds this depth, disconnect it
# rather than consuming unbounded memory (§7).
_MAX_SEND_QUEUE_DEPTH = 64


class ConnectionManager:
    """Owns the channel → WebSocket registry for this process."""

    def __init__(self) -> None:
        # channel → set of connected websockets
        self._subscriptions: dict[str, set[WebSocket]] = {}
        # websocket → set of channels it's subscribed to (reverse index)
        self._connections: dict[WebSocket, set[str]] = {}
        # websocket → bounded asyncio.Queue for backpressure
        self._send_queues: dict[WebSocket, asyncio.Queue[dict[str, Any]]] = {}
        # websocket → background sender task
        self._sender_tasks: dict[WebSocket, asyncio.Task[None]] = {}

    @property
    def active_connection_count(self) -> int:
        """Number of active WebSocket connections."""
        return len(self._connections)

    async def connect(self, websocket: WebSocket, channels: list[str]) -> None:
        """Register a WebSocket for the given channels and start its sender."""
        self._connections[websocket] = set(channels)
        for channel in channels:
            if channel not in self._subscriptions:
                self._subscriptions[channel] = set()
            self._subscriptions[channel].add(websocket)

        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=_MAX_SEND_QUEUE_DEPTH)
        self._send_queues[websocket] = queue
        self._sender_tasks[websocket] = asyncio.create_task(self._sender_loop(websocket, queue))

        _logger.info(
            "ws_connected",
            channels=channels,
            active_connections=self.active_connection_count,
        )

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket from all channels and cancel its sender."""
        channels = self._connections.pop(websocket, set())
        for channel in channels:
            subs = self._subscriptions.get(channel)
            if subs:
                subs.discard(websocket)
                if not subs:
                    del self._subscriptions[channel]

        self._send_queues.pop(websocket, None)
        task = self._sender_tasks.pop(websocket, None)
        if task and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        _logger.info(
            "ws_disconnected",
            active_connections=self.active_connection_count,
        )

    def subscribe(self, websocket: WebSocket, channel: str) -> None:
        """Add a channel subscription for an already-connected socket."""
        if websocket not in self._connections:
            return
        self._connections[websocket].add(channel)
        if channel not in self._subscriptions:
            self._subscriptions[channel] = set()
        self._subscriptions[channel].add(websocket)

    async def broadcast(self, channel: str, message: dict[str, Any]) -> None:
        """Enqueue a message to all WebSockets subscribed to ``channel``.

        If a client's queue is full (backpressure), disconnect it immediately
        rather than blocking the broadcast to other clients.
        """
        sockets = self._subscriptions.get(channel)
        if not sockets:
            return

        disconnected: list[WebSocket] = []
        for ws in sockets:
            queue = self._send_queues.get(ws)
            if queue is None:
                disconnected.append(ws)
                continue
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                _logger.warning("ws_backpressure_disconnect", channel=channel)
                disconnected.append(ws)

        for ws in disconnected:
            await self.disconnect(ws)

    def get_subscribed_channels(self) -> list[str]:
        """Return the list of channels with at least one subscriber."""
        return list(self._subscriptions.keys())

    async def _sender_loop(
        self, websocket: WebSocket, queue: asyncio.Queue[dict[str, Any]]
    ) -> None:
        """Drain the per-connection queue, sending each message as JSON."""
        try:
            while True:
                message = await queue.get()
                try:
                    await websocket.send_json(message)
                except Exception:  # noqa: BLE001 - send failure means the socket is gone
                    _logger.debug("ws_send_failed")
                    await self.disconnect(websocket)
                    return
        except asyncio.CancelledError:
            return
