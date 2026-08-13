"""Adapts `infrastructure.jobs.pool.JobQueue` to `application.common.ports.
JobQueuePort` — unwraps `arq`'s `Job | None` return into a plain
`str | None` job id, so `arq` types never cross into the application layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lpg.infrastructure.jobs.pool import JobQueue


class OrderJobQueueAdapter:
    def __init__(self, job_queue: JobQueue) -> None:
        self._job_queue = job_queue

    async def enqueue(self, function_name: str, *args: Any, **kwargs: Any) -> str | None:
        job = await self._job_queue.enqueue(function_name, *args, **kwargs)
        return job.job_id if job is not None else None
