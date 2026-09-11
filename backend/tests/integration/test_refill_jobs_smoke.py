"""`predict_refill_due_for_tenant` against a real Postgres + Redis — the
daily refill-due prediction + proactive nudge job (AI Operational
Intelligence, Horizon 1 Stage 2).

Seeds a `customer_refill` feature snapshot directly (Stage 1's own build
job is exercised by `test_feature_store_jobs_smoke.py`; this test's
concern is the prediction + nudge logic that consumes one, not how the
snapshot itself gets built) with a chosen `avg_refill_interval_days` so the
predicted due date lands inside the configured lead window, then verifies:
the `ai.prediction` row, the customer's `refill_due_customer` notification
actually getting enqueued (opted in via `refill_nudge_enabled`), and the
dedupe gate suppressing a second nudge on a same-day re-run.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration

_ADMIN_URL = "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:5433/lpg_test"


async def _seed_tenant_with_snapshot(
    engine: AsyncEngine, *, last_delivered_days_ago: int, avg_refill_interval_days: float
) -> tuple[uuid.UUID, uuid.UUID]:
    """tenant -> branch -> customer, plus one `ai.feature_snapshot` row
    inserted directly (not via the Stage 1 build job — see module
    docstring). Returns `(tenant_id, customer_id)`."""
    today = datetime.now(UTC).date()
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'Refill Smoke', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"refill-smoke-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
        branch_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.branch (id, tenant_id, name) "
                    "VALUES (gen_random_uuid(), :t, 'Refill Smoke Branch') RETURNING id"
                ),
                {"t": str(tenant_id)},
            )
        ).scalar_one()
        customer_id = (
            await conn.execute(
                text(
                    "INSERT INTO customer.customer "
                    "(id, tenant_id, branch_id, customer_type, full_name, phone_number, "
                    "consumer_number) "
                    "VALUES (gen_random_uuid(), :t, :b, 'domestic', 'Refill Smoke Customer', "
                    ":phone, :cn) RETURNING id"
                ),
                {
                    "t": str(tenant_id),
                    "b": str(branch_id),
                    "phone": f"9{uuid.uuid4().int % 10**9:09d}",
                    "cn": f"CN-{uuid.uuid4().hex[:8]}",
                },
            )
        ).scalar_one()
        last_delivered_at = datetime.now(UTC) - timedelta(days=last_delivered_days_ago)
        await conn.execute(
            text(
                "INSERT INTO ai.feature_snapshot "
                "(id, tenant_id, entity_type, entity_id, as_of_date, features) "
                "VALUES (gen_random_uuid(), :t, 'customer_refill', :c, :as_of, "
                "CAST(:features AS jsonb))"
            ),
            {
                "t": str(tenant_id),
                "c": str(customer_id),
                "as_of": today,
                "features": (
                    '{"last_delivered_at": "'
                    + last_delivered_at.isoformat()
                    + '", "delivery_count": 5, "avg_refill_interval_days": '
                    + str(avg_refill_interval_days)
                    + ', "branch_id": "'
                    + str(branch_id)
                    + '", "primary_cylinder_type_id": null}'
                ),
            },
        )
        for key, value in (
            ("refill_nudge_enabled", "true"),
            ("refill_nudge_lead_days", "5"),
            ("refill_nudge_min_gap_days", "3"),
        ):
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant_configuration "
                    "(id, tenant_id, config_key, config_value, effective_from) "
                    "VALUES (gen_random_uuid(), :t, :key, CAST(:value AS jsonb), now())"
                ),
                {"t": str(tenant_id), "key": key, "value": value},
            )
    return (uuid.UUID(str(tenant_id)), uuid.UUID(str(customer_id)))


async def _run_for_tenant(integration_settings: Settings, tenant_id: uuid.UUID) -> tuple[int, int]:
    from lpg.application.common.tenant import RequestTenantContext
    from lpg.infrastructure.jobs.pool import JobQueue
    from lpg.infrastructure.jobs.refill_jobs import predict_refill_due_for_tenant
    from lpg.infrastructure.persistence.database import build_database
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
    from lpg.infrastructure.security.field_encryption import FernetFieldEncryptor

    field_encryptor = FernetFieldEncryptor(integration_settings)
    database = build_database(integration_settings)
    database.connect()
    job_queue = JobQueue(integration_settings)
    await job_queue.connect()
    try:
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(
                session, RequestTenantContext(tenant_id=tenant_id)
            ) as uow:
                return await predict_refill_due_for_tenant(
                    uow,
                    job_queue,
                    field_encryptor,
                    tenant_id=tenant_id,
                    as_of=datetime.now(UTC).date(),
                )
        return (0, 0)
    finally:
        await database.disconnect()
        await job_queue.disconnect()


async def test_predicts_and_nudges_a_customer_due_soon(
    integration_settings: Settings, postgres_available: bool
) -> None:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable")

    engine = create_async_engine(_ADMIN_URL)
    try:
        # last delivery 17 days ago + a 20-day interval -> due in 3 days,
        # inside the 5-day lead window configured above; 17 days since
        # last delivery clears the 3-day minimum gap.
        tenant_id, customer_id = await _seed_tenant_with_snapshot(
            engine, last_delivered_days_ago=17, avg_refill_interval_days=20.0
        )

        written, sent = await _run_for_tenant(integration_settings, tenant_id)
        assert written == 1
        assert sent == 1

        async with engine.begin() as conn:
            prediction_rows = (
                await conn.execute(
                    text(
                        "SELECT prediction_type, model_version, value "
                        "FROM ai.prediction WHERE tenant_id = :t AND subject_id = :c"
                    ),
                    {"t": str(tenant_id), "c": str(customer_id)},
                )
            ).mappings().all()
            nudge_sent_at = (
                await conn.execute(
                    text(
                        "SELECT last_refill_nudge_sent_at FROM customer.customer WHERE id = :c"
                    ),
                    {"c": str(customer_id)},
                )
            ).scalar_one()

        assert len(prediction_rows) == 1
        assert prediction_rows[0]["prediction_type"] == "refill_due"
        assert prediction_rows[0]["model_version"] == "refill_heuristic_v1"
        assert prediction_rows[0]["value"]["interval_days"] == 20.0
        assert nudge_sent_at is not None

        # Re-run the same day: a new prediction is still recorded (the
        # traceable read model refreshes daily), but the dedupe gate
        # suppresses a second nudge for the same due cycle.
        written_again, sent_again = await _run_for_tenant(integration_settings, tenant_id)
        assert written_again == 1
        assert sent_again == 0

        # Cleanup — mirrors `test_feature_store_jobs_smoke.py`'s own
        # ordering (children before the `tenant.tenant` row itself).
        async with engine.begin() as conn:
            for stmt in (
                "DELETE FROM ai.prediction WHERE tenant_id = :t",
                "DELETE FROM ai.feature_snapshot WHERE tenant_id = :t",
                "DELETE FROM tenant.tenant_configuration WHERE tenant_id = :t",
                "DELETE FROM customer.customer WHERE tenant_id = :t",
                "DELETE FROM tenant.branch WHERE tenant_id = :t",
                "DELETE FROM tenant.tenant WHERE id = :t",
            ):
                await conn.execute(text(stmt), {"t": str(tenant_id)})
    finally:
        await engine.dispose()
