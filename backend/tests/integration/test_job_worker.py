"""ARQ worker round-trip, against real Redis (ADR-029).

Proves the infrastructure works end to end: enqueue via ``JobQueue`` (the API
process's side), process via a real ``arq.worker.Worker`` running the same
``ping`` function the real worker entry point registers (the worker
process's side), and read the result back. No business job exists yet — this
is the round trip the future ones will rely on.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from lpg.infrastructure.jobs.pool import JobQueue

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration


@pytest.fixture
async def job_queue(
    integration_settings: Settings, redis_available: bool
) -> AsyncIterator[JobQueue]:
    if not redis_available:
        pytest.skip("Redis is not reachable — start it with ./scripts/dev-up.sh")
    queue = JobQueue(integration_settings)
    await queue.connect()
    try:
        yield queue
    finally:
        await queue.disconnect()


class TestJobQueue:
    async def test_ping_is_true_once_connected(self, job_queue: JobQueue) -> None:
        assert await job_queue.ping() is True

    async def test_enqueue_returns_a_job(self, job_queue: JobQueue) -> None:
        from lpg.infrastructure.jobs.worker import ping

        job = await job_queue.enqueue(ping.__name__)

        assert job is not None


class TestWorkerRoundTrip:
    async def test_enqueued_ping_is_processed_and_returns_pong(
        self, job_queue: JobQueue, integration_settings: Settings
    ) -> None:
        from arq.connections import RedisSettings
        from arq.worker import Worker

        from lpg.infrastructure.jobs.worker import ping

        job = await job_queue.enqueue(ping.__name__)
        assert job is not None

        # Burst mode: process whatever is currently queued, then exit — the
        # standard way to test an ARQ worker without running it forever.
        worker = Worker(
            functions=[ping],
            redis_settings=RedisSettings.from_dsn(str(integration_settings.redis_url)),
            burst=True,
            poll_delay=0,
        )
        await worker.main()
        await worker.close()

        result = await job.result(timeout=5)
        assert result == "pong"
