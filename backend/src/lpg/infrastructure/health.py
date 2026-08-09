"""Health-check adapters.

Wraps concrete infrastructure clients as the application layer's ``HealthCheck``
port, so the readiness endpoint can report dependency status without the API
layer importing SQLAlchemy or Redis types.

That indirection is not ceremony — it was added because the ``import-linter``
contract "SQLAlchemy stays inside infrastructure" failed when the health router
imported ``Database`` directly, even under ``TYPE_CHECKING``. The boundary
check earned its place on its first run.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lpg.infrastructure.jobs.pool import JobQueue
    from lpg.infrastructure.persistence.database import Database
    from lpg.infrastructure.redis.client import RedisClient
    from lpg.infrastructure.storage.client import S3CompatibleFileStorage


class DatabaseHealthCheck:
    """Reports whether PostgreSQL is reachable."""

    def __init__(self, database: Database) -> None:
        self._database = database

    @property
    def name(self) -> str:
        return "postgresql"

    async def check(self) -> bool:
        return await self._database.ping()


class RedisHealthCheck:
    """Reports whether Redis is reachable."""

    def __init__(self, client: RedisClient) -> None:
        self._client = client

    @property
    def name(self) -> str:
        return "redis"

    async def check(self) -> bool:
        return await self._client.ping()


class JobQueueHealthCheck:
    """Reports whether the ARQ job queue's Redis connection is reachable."""

    def __init__(self, queue: JobQueue) -> None:
        self._queue = queue

    @property
    def name(self) -> str:
        return "job_queue"

    async def check(self) -> bool:
        return await self._queue.ping()


class StorageHealthCheck:
    """Reports whether object storage (the configured bucket) is reachable."""

    def __init__(self, storage: S3CompatibleFileStorage) -> None:
        self._storage = storage

    @property
    def name(self) -> str:
        return "storage"

    async def check(self) -> bool:
        return await self._storage.ping()
