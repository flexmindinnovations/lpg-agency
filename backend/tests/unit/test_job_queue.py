"""``JobQueue`` — no Redis required for these."""

from __future__ import annotations

import pytest

from lpg.config.settings import Settings
from lpg.infrastructure.jobs.pool import JobQueue


class TestBeforeConnect:
    async def test_ping_returns_false_before_connect(self) -> None:
        queue = JobQueue(Settings(environment="local"))

        assert await queue.ping() is False

    async def test_enqueue_raises_before_connect(self) -> None:
        queue = JobQueue(Settings(environment="local"))

        with pytest.raises(RuntimeError, match="connect"):
            await queue.enqueue("ping")

    async def test_disconnect_before_connect_is_a_safe_no_op(self) -> None:
        queue = JobQueue(Settings(environment="local"))

        await queue.disconnect()  # must not raise
