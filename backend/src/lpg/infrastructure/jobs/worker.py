from arq import cron
from lpg.infrastructure.jobs.refresh_views import refresh_materialized_views
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
from lpg.infrastructure.jobs.notification_jobs import send_notification

if TYPE_CHECKING:
    from lpg.infrastructure.persistence.database import Database

_logger = get_logger(__name__)


async def ping(ctx: dict[str, Any]) -> str:  # noqa: ARG001 - ARQ's job-function signature
    """Infrastructure round-trip proof. Not a business job."""
    structlog.contextvars.bind_contextvars(correlation_id=str(uuid.uuid4()), job_name="ping")
    _logger.info("job_ping_executed")
    return "pong"


async def bulk_cancel_orders(
    ctx: dict[str, Any],
    *,
    tenant_id: str,
    order_ids: list[str],
    reason: str,
    cancelled_by: str,
) -> dict[str, int]:
    """Cancels each order in `order_ids` one at a time, tenant-scoped.

    The first real business job (Order Management) — enqueued by
    `BulkCancelOrdersUseCase` when a bulk-cancel request exceeds
    `BULK_CANCEL_SYNC_THRESHOLD` (50) orders. Idempotent: `CancelOrderUseCase`
    itself is idempotent per order — `cancel_free()`/`request_cancellation_
    approval()` both raise `INVALID_STATE_TRANSITION` on an order that's
    already `cancelled`, so a retried job re-running this function only
    re-attempts orders that didn't already succeed, and double-firing on an
    already-cancelled order is a caught, logged failure, not a corruption.
    """
    structlog.contextvars.bind_contextvars(
        correlation_id=str(uuid.uuid4()), job_name="bulk_cancel_orders", tenant_id=tenant_id
    )
    database: Database = ctx["database"]

    from lpg.application.common.errors import NotFoundError
    from lpg.application.common.tenant import RequestTenantContext
    from lpg.application.order.use_cases import CancelOrderCommand, CancelOrderUseCase
    from lpg.infrastructure.persistence.repositories.inventory import (
        SqlAlchemyInventoryLocationRepository,
    )
    from lpg.infrastructure.persistence.repositories.order import (
        SqlAlchemyCancellationRecordRepository,
        SqlAlchemyOrderRepository,
    )
    from lpg.infrastructure.persistence.repositories.route import SqlAlchemyRouteRepository
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    tenant_uuid = uuid.UUID(tenant_id)
    cancelled_by_uuid = uuid.UUID(cancelled_by)
    succeeded = 0
    failed = 0

    for order_id in order_ids:
        async for session in database.open_session(tenant_id=tenant_uuid):
            tenant_context = RequestTenantContext(tenant_id=tenant_uuid)
            async with SqlAlchemyUnitOfWork(session, tenant_context) as uow:
                order_repository = SqlAlchemyOrderRepository(uow)
                route_repository = SqlAlchemyRouteRepository(uow)
                inventory_repository = SqlAlchemyInventoryLocationRepository(uow)
                cancellation_repository = SqlAlchemyCancellationRecordRepository(uow)
                use_case = CancelOrderUseCase(
                    order_repository,
                    route_repository,
                    inventory_repository,
                    cancellation_repository,
                    uow,
                )
                try:
                    await use_case.execute(
                        CancelOrderCommand(
                            order_id=uuid.UUID(order_id),
                            reason=reason,
                            cancelled_by=cancelled_by_uuid,
                        )
                    )
                except NotFoundError:
                    failed += 1
                except Exception:
                    failed += 1
                    _logger.warning("bulk_cancel_order_failed", order_id=order_id, exc_info=True)
                else:
                    succeeded += 1

    _logger.info("job_bulk_cancel_orders_executed", succeeded=succeeded, failed=failed)
    return {"succeeded": succeeded, "failed": failed}


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

    cron_jobs = [
        cron(refresh_materialized_views, hour=2, minute=0)  # Run nightly at 2:00 AM
    ]

    functions = (ping, bulk_cancel_orders, send_notification)
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(str(get_settings().redis_url))
    # A job that raises is retried; capped so a permanently-broken job
    # (bad input, not a transient failure) does not retry forever.
    max_tries = 5
