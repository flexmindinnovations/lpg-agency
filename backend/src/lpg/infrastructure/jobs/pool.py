"""Access to the ARQ job queue for **enqueuing** work from the API process.

Distinct from the worker (``lpg.infrastructure.jobs.worker``), which
*processes* the queue — request-handling code that wants to schedule
background work uses this instead, the same way the API process uses
``Database``/``RedisClient`` without being the thing that runs migrations or
serves cache reads to itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lpg.config.logging import get_logger

if TYPE_CHECKING:
    from arq.connections import ArqRedis
    from arq.jobs import Job

    from lpg.config.settings import Settings

_logger = get_logger(__name__)


class JobQueue:
    """Owns the ARQ connection pool used to enqueue jobs."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._pool: ArqRedis | None = None

    async def connect(self) -> None:
        from arq import create_pool
        from arq.connections import RedisSettings

        self._pool = await create_pool(RedisSettings.from_dsn(str(self._settings.redis_url)))
        _logger.info("job_queue_connected")

    async def disconnect(self) -> None:
        if self._pool is not None:
            await self._pool.aclose()
            self._pool = None
            _logger.info("job_queue_disconnected")

    async def enqueue(self, function_name: str, *args: Any, **kwargs: Any) -> Job | None:
        """Enqueue a job by its registered ARQ function name.

        Returns ``None`` if a job with the same explicit ``_job_id`` is
        already queued — ARQ's own idempotency primitive, which every real
        job's call site should use (a stable, deterministic ``_job_id``
        derived from business identifiers) rather than relying on the
        Idempotency-Key infrastructure, which protects HTTP requests, not
        job scheduling.
        """
        if self._pool is None:
            msg = "JobQueue.connect() has not been called"
            raise RuntimeError(msg)
        return await self._pool.enqueue_job(function_name, *args, **kwargs)

    async def ping(self) -> bool:
        """Whether the queue's Redis connection is reachable. Used by readiness."""
        if self._pool is None:
            return False
        try:
            await self._pool.ping()
        except Exception as exc:  # noqa: BLE001 - readiness reports, never raises
            _logger.warning("job_queue_ping_failed", error=str(exc))
            return False
        return True


def build_job_queue(settings: Settings | None = None) -> JobQueue:
    """Construct a JobQueue from settings."""
    from lpg.config.settings import get_settings

    return JobQueue(settings or get_settings())
