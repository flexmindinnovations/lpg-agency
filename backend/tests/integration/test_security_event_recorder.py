"""`SqlAlchemySecurityEventRecorder` against real PostgreSQL: the rows land under
the right tenant (or the platform sentinel), respect RLS, and carry request
context but never a secret."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
import structlog
from sqlalchemy import text

from lpg.application.audit import security_events as sec
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.security_event_recorder import (
    PLATFORM_SENTINEL_TENANT_ID,
    SqlAlchemySecurityEventRecorder,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration


@pytest.fixture
async def database(
    integration_settings: Settings, postgres_available: bool
) -> AsyncIterator[Database]:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable — start it with ./scripts/dev-up.sh")
    db = Database(integration_settings)
    db.connect()
    try:
        yield db
    finally:
        await db.disconnect()


async def _seed_tenant(admin_engine: AsyncEngine) -> uuid.UUID:
    async with admin_engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug) "
                    "VALUES (gen_random_uuid(), 'Sec Events', :slug) RETURNING id"
                ),
                {"slug": f"sec-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
    return uuid.UUID(str(tenant_id))


async def _rows(admin_engine: AsyncEngine, action: str, subject: str) -> list[dict[str, object]]:
    async with admin_engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT tenant_id, actor_id, entity_name, action, correlation_id, metadata, "
                "after_state "
                "FROM audit.audit_log WHERE action = :action "
                "AND metadata->>'subject' = :subject"
            ),
            {"action": action, "subject": subject},
        )
        return [dict(row._mapping) for row in result]


class TestSecurityEventRecorder:
    async def test_a_login_is_written_under_the_users_tenant_with_request_context(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id, user_id = await _seed_tenant(admin_engine), uuid.uuid4()
        subject = f"{uuid.uuid4().hex[:6]}***@example.com"
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            correlation_id="corr-123", client_ip="203.0.113.9", user_agent="LpgDriver/1.0"
        )
        try:
            await SqlAlchemySecurityEventRecorder(database).record(
                sec.SecurityEvent(
                    action=sec.LOGIN,
                    outcome="success",
                    tenant_id=tenant_id,
                    user_id=user_id,
                    subject=subject,
                )
            )
        finally:
            structlog.contextvars.clear_contextvars()

        (row,) = await _rows(admin_engine, sec.LOGIN, subject)
        assert row["tenant_id"] == tenant_id
        assert row["actor_id"] == user_id
        assert row["entity_name"] == sec.ENTITY_NAME
        assert row["correlation_id"] == "corr-123"
        assert row["metadata"]["client_ip"] == "203.0.113.9"  # type: ignore[index]
        assert row["metadata"]["user_agent"] == "LpgDriver/1.0"  # type: ignore[index]
        assert row["metadata"]["outcome"] == "success"  # type: ignore[index]
        assert row["after_state"]["client_ip"] == "203.0.113.9"  # type: ignore[index]

    async def test_an_event_with_no_tenant_goes_to_the_platform_sentinel(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        subject = f"{uuid.uuid4().hex[:6]}***@example.com"

        await SqlAlchemySecurityEventRecorder(database).record(
            sec.SecurityEvent(
                action=sec.LOGIN_FAILED,
                outcome="failure",
                subject=subject,
                reason="unknown_account",
            )
        )

        (row,) = await _rows(admin_engine, sec.LOGIN_FAILED, subject)
        assert row["tenant_id"] == PLATFORM_SENTINEL_TENANT_ID
        assert row["metadata"]["reason"] == "unknown_account"  # type: ignore[index]

    async def test_a_non_persistent_event_writes_no_row(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        subject = f"{uuid.uuid4().hex[:6]}***@example.com"

        await SqlAlchemySecurityEventRecorder(database).record(
            sec.SecurityEvent(
                action=sec.TOKEN_REFRESHED, outcome="success", subject=subject, persist=False
            )
        )

        assert await _rows(admin_engine, sec.TOKEN_REFRESHED, subject) == []

    async def test_a_database_failure_never_reaches_the_sign_in_flow(
        self, integration_settings: Settings
    ) -> None:
        unconnected = Database(integration_settings)  # connect() never called

        await SqlAlchemySecurityEventRecorder(unconnected).record(
            sec.SecurityEvent(action=sec.LOGOUT, outcome="success", tenant_id=uuid.uuid4())
        )
