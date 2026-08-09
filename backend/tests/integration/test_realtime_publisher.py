"""``RedisRealtimePublisher``, against real Redis.

Proves the publish path actually works end-to-end — a real subscriber on
the channel receives the message, JSON-decoded back to the same dict — not
just that ``publish()`` doesn't raise. Mirrors the worker's ``ping``-job
proof from Phase 2: a trivial round trip through real infrastructure, not a
business feature.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import TYPE_CHECKING

import pytest

from lpg.infrastructure.realtime.publisher import RedisRealtimePublisher
from lpg.infrastructure.redis.client import RedisClient

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration


@pytest.fixture
async def publisher(
    integration_settings: Settings, redis_available: bool
) -> AsyncIterator[RedisRealtimePublisher]:
    if not redis_available:
        pytest.skip("Redis is not reachable — start it with ./scripts/dev-up.sh")
    client = RedisClient(integration_settings)
    client.connect()
    try:
        yield RedisRealtimePublisher(client)
    finally:
        await client.disconnect()


class TestPublish:
    async def test_a_real_subscriber_receives_the_published_message(
        self, publisher: RedisRealtimePublisher, integration_settings: Settings
    ) -> None:
        import redis.asyncio as redis_asyncio

        channel = f"tenant:{uuid.uuid4()}:order:{uuid.uuid4()}"
        message = {"event": "order.status_changed", "status": "delivered", "version": 3}

        redis_client = redis_asyncio.from_url(  # type: ignore[no-untyped-call]
            str(integration_settings.redis_url), decode_responses=True
        )
        pubsub = redis_client.pubsub()
        try:
            await pubsub.subscribe(channel)
            # The subscribe confirmation is itself a message; discard it before
            # publishing, so the next message received is the real payload.
            await pubsub.get_message(timeout=2.0)

            await publisher.publish(channel, message)

            received = await asyncio.wait_for(
                pubsub.get_message(ignore_subscribe_messages=True, timeout=2.0),
                timeout=3.0,
            )

            assert received is not None
            assert json.loads(received["data"]) == message
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
            await redis_client.aclose()

    async def test_publishing_to_a_channel_with_no_subscriber_does_not_raise(
        self, publisher: RedisRealtimePublisher
    ) -> None:
        channel = f"tenant:{uuid.uuid4()}:dashboard"

        await publisher.publish(channel, {"event": "kpi.refresh"})
