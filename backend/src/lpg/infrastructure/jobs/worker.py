"""ARQ worker entry point (ADR-029).

Run with::

    uv run arq lpg.infrastructure.jobs.worker.WorkerSettings

**Entry-point module, like `lpg.api.app`.** ``WorkerSettings.redis_settings``
must be a class attribute ARQ's CLI can read without calling any function —
so, like the API's ``app = create_app()``, this module constructs real
``Settings()`` at import time. Never import this module at test-collection
time; defer the import inside a function, exactly as every test in this
codebase already does for ``lpg.api.app`` (see any of `tests/integration
/test_tenant_dependency_chain.py`'s fixtures for why).

**The contract every future job function must satisfy** (Phase 2 instructs
establishing this, not writing business jobs against it yet):

- **Tenant-scoped** — a job that acts across tenants iterates them and sets
  the tenant context (``Database.open_session(tenant_id=...)``) once per
  tenant inside the loop; nothing ever runs unscoped (ADR-017,
  ``06-database-architecture.md`` §2.2).
- **Idempotent** — safe to execute twice with the same input. Scheduled jobs
  must tolerate double-firing; retried jobs must not double-apply their
  effect.
- **Observable** — structured logging via ``lpg.config.logging``, with a
  correlation ID generated per job run (there is no inbound request to carry
  one from) and bound to ``structlog.contextvars`` before any work starts,
  matching the API's per-request pattern (`12-observability.md` §4).
- **Retry-safe** — ARQ retries a job that raises, by default. A job must not
  leave the system in a state a retry would corrupt (partial, non-idempotent
  side effects are the specific failure mode this rules out).

No business job exists yet. ``ping`` is infrastructure only — proof the
worker round-trips through Redis, nothing more.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog
from arq.connections import RedisSettings

from lpg.config.logging import configure_logging, get_logger
from lpg.config.settings import get_settings
from lpg.infrastructure.persistence.database import build_database

if TYPE_CHECKING:
    from lpg.infrastructure.persistence.database import Database

_logger = get_logger(__name__)


async def ping(ctx: dict[str, Any]) -> str:  # noqa: ARG001 - ARQ's job-function signature
    """Infrastructure round-trip proof. Not a business job."""
    structlog.contextvars.bind_contextvars(correlation_id=str(uuid.uuid4()), job_name="ping")
    _logger.info("job_ping_executed")
    return "pong"


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    configure_logging(level=settings.log_level, json_output=settings.log_json)

    database = build_database(settings)
    database.connect()
    ctx["database"] = database

    _logger.info("worker_started", environment=settings.environment)


async def shutdown(ctx: dict[str, Any]) -> None:
    database: Database | None = ctx.get("database")
    if database is not None:
        await database.disconnect()
    _logger.info("worker_stopped")


class WorkerSettings:
    """ARQ reads these as class attributes — see module docstring."""

    functions = (ping,)
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(str(get_settings().redis_url))
    # A job that raises is retried; capped so a permanently-broken job
    # (bad input, not a transient failure) does not retry forever.
    max_tries = 5
