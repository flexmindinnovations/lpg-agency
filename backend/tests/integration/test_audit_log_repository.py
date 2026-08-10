"""`SqlAlchemyAuditLogRepository`, against a real PostgreSQL — the first
read path `audit.audit_log` has ever had (Phase 2 built it write-only).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from lpg.application.audit.list_audit_log import ListAuditLogQuery, ListAuditLogUseCase
from lpg.application.common.tenant import RequestTenantContext
from lpg.application.tenant.branch import CreateBranchCommand, CreateBranchUseCase
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.repositories.audit import SqlAlchemyAuditLogRepository
from lpg.infrastructure.persistence.repositories.tenant import SqlAlchemyBranchRepository
from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

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
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'Audit Test Co', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"audit-test-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
    return uuid.UUID(str(tenant_id))


async def _seed_audit_row(
    admin_engine: AsyncEngine,
    *,
    tenant_id: uuid.UUID,
    entity_name: str,
    performed_at: datetime,
    action: str = "create",
) -> uuid.UUID:
    async with admin_engine.begin() as conn:
        entry_id = (
            await conn.execute(
                text(
                    "INSERT INTO audit.audit_log "
                    "(id, tenant_id, entity_name, entity_id, action, performed_at) "
                    "VALUES (gen_random_uuid(), :tenant_id, :entity_name, "
                    "gen_random_uuid()::text, :action, :performed_at) RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "entity_name": entity_name,
                    "action": action,
                    "performed_at": performed_at,
                },
            )
        ).scalar_one()
    return uuid.UUID(str(entry_id))


class TestRealWritePathIsReadable:
    async def test_a_branch_creation_produces_a_readable_audit_row(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        context = RequestTenantContext(tenant_id=tenant_id)

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                use_case = CreateBranchUseCase(SqlAlchemyBranchRepository(uow), uow)
                await use_case.execute(CreateBranchCommand(tenant_id=tenant_id, name="Nashik West"))

        query_use_case = ListAuditLogUseCase(SqlAlchemyAuditLogRepository(database))
        page = await query_use_case.execute(
            ListAuditLogQuery(tenant_id=tenant_id, entity_name="branch")
        )

        assert len(page.items) == 1
        assert page.items[0].entity_name == "branch"
        assert page.items[0].action == "create"
        assert page.items[0].after_state is not None
        assert page.items[0].after_state["name"] == "Nashik West"


class TestPaginationAndFiltering:
    async def test_pages_most_recent_first_and_the_cursor_advances_correctly(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        now = datetime.now(UTC)
        # Oldest to newest — expect pages in the reverse order.
        for i in range(5):
            await _seed_audit_row(
                admin_engine,
                tenant_id=tenant_id,
                entity_name="widget",
                performed_at=now - timedelta(minutes=5 - i),
            )

        use_case = ListAuditLogUseCase(SqlAlchemyAuditLogRepository(database))
        first_page = await use_case.execute(ListAuditLogQuery(tenant_id=tenant_id, limit=3))
        assert len(first_page.items) == 3
        assert first_page.next_cursor is not None
        # Most recent first.
        assert first_page.items[0].performed_at > first_page.items[1].performed_at

        second_page = await use_case.execute(
            ListAuditLogQuery(tenant_id=tenant_id, limit=3, cursor=first_page.next_cursor)
        )
        assert len(second_page.items) == 2
        assert second_page.next_cursor is None
        # No overlap between pages.
        first_ids = {item.id for item in first_page.items}
        second_ids = {item.id for item in second_page.items}
        assert first_ids.isdisjoint(second_ids)

    async def test_filters_by_entity_name(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        now = datetime.now(UTC)
        await _seed_audit_row(
            admin_engine, tenant_id=tenant_id, entity_name="branch", performed_at=now
        )
        await _seed_audit_row(
            admin_engine, tenant_id=tenant_id, entity_name="warehouse", performed_at=now
        )

        use_case = ListAuditLogUseCase(SqlAlchemyAuditLogRepository(database))
        page = await use_case.execute(ListAuditLogQuery(tenant_id=tenant_id, entity_name="branch"))

        assert len(page.items) == 1
        assert page.items[0].entity_name == "branch"

    async def test_filters_by_date_range(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        now = datetime.now(UTC)
        await _seed_audit_row(
            admin_engine,
            tenant_id=tenant_id,
            entity_name="widget",
            performed_at=now - timedelta(days=30),
        )
        in_range_id = await _seed_audit_row(
            admin_engine, tenant_id=tenant_id, entity_name="widget", performed_at=now
        )

        use_case = ListAuditLogUseCase(SqlAlchemyAuditLogRepository(database))
        page = await use_case.execute(
            ListAuditLogQuery(
                tenant_id=tenant_id,
                date_from=now - timedelta(days=1),
                date_to=now + timedelta(days=1),
            )
        )

        assert len(page.items) == 1
        assert page.items[0].id == in_range_id

    async def test_cannot_see_another_tenants_audit_rows(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        own_tenant = await _seed_tenant(admin_engine)
        other_tenant = await _seed_tenant(admin_engine)
        now = datetime.now(UTC)
        await _seed_audit_row(
            admin_engine, tenant_id=other_tenant, entity_name="widget", performed_at=now
        )

        use_case = ListAuditLogUseCase(SqlAlchemyAuditLogRepository(database))
        page = await use_case.execute(ListAuditLogQuery(tenant_id=own_tenant))

        assert page.items == []
