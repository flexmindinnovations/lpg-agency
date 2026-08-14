from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
import structlog
from arq import cron

from lpg.config.logging import get_logger

if TYPE_CHECKING:
    from lpg.infrastructure.persistence.database import Database

_logger = get_logger(__name__)


async def refresh_materialized_views(ctx: dict[str, Any]) -> None:
    """Cron job: refreshes all reporting materialized views concurrently.

    Runs nightly to update GST filing periods, customer consumption metrics,
    and driver performance aggregates without blocking concurrent report reads.
    """
    structlog.contextvars.bind_contextvars(
        correlation_id=str(uuid.uuid4()), job_name="refresh_materialized_views"
    )
    database: Database = ctx["database"]

    _logger.info("job_refresh_materialized_views_started")

    # The views to refresh. Order does not matter as they don't depend on each other.
    views_to_refresh = [
        "rpt.mv_gst_filing_period",
        "rpt.mv_customer_consumption",
        "rpt.mv_driver_performance_daily",
    ]

    async for session in database.open_session(tenant_id=None):
        for view in views_to_refresh:
            try:
                # CONCURRENTLY requires a unique index on the materialized view
                await session.execute(sa.text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}"))
                _logger.info("materialized_view_refreshed", view=view)
            except Exception:
                _logger.exception("materialized_view_refresh_failed", view=view)

    _logger.info("job_refresh_materialized_views_completed")
