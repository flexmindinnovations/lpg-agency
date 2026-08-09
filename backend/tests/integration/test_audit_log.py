"""`AuditRecorder` and `audit.audit_log`, against a real PostgreSQL.

Exercised through the real seam — `SqlAlchemyUnitOfWork` + `SqlAlchemyTenantRepository`
— rather than constructing `AuditLogModel` rows directly, since the point is
proving the `before_flush` hook actually fires for real ORM mutations, not
that the model class itself is well-formed.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from lpg.application.common.tenant import RequestTenantContext
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.repositories.tenant import SqlAlchemyTenantRepository
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


async def _seed_tenant(admin_engine: AsyncEngine, *, name: str) -> uuid.UUID:
    async with admin_engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug) "
                    "VALUES (gen_random_uuid(), :name, :slug) RETURNING id"
                ),
                {"name": name, "slug": f"audit-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
    return uuid.UUID(str(tenant_id))


async def _audit_rows_for(
    admin_engine: AsyncEngine, entity_id: uuid.UUID
) -> list[dict[str, object]]:
    async with admin_engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT action, entity_name, tenant_id, actor_id, before_state, "
                "after_state, correlation_id FROM audit.audit_log "
                "WHERE entity_id = :entity_id ORDER BY performed_at"
            ),
            {"entity_id": str(entity_id)},
        )
        return [dict(row._mapping) for row in result]


class TestAuditRowOnUpdate:
    async def test_a_rename_produces_exactly_one_audit_row(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine, name="Audited Co")
        context = RequestTenantContext(tenant_id=tenant_id, user_id=uuid.uuid4())

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repository = SqlAlchemyTenantRepository(uow)
                tenant = await repository.get(tenant_id)
                assert tenant is not None
                tenant.rename("Audited Co Renamed")
                await repository.save(tenant)

        rows = await _audit_rows_for(admin_engine, tenant_id)
        assert len(rows) == 1

    async def test_the_row_captures_actor_tenant_action_and_state(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine, name="Before")
        actor_id = uuid.uuid4()
        context = RequestTenantContext(tenant_id=tenant_id, user_id=actor_id)

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repository = SqlAlchemyTenantRepository(uow)
                tenant = await repository.get(tenant_id)
                assert tenant is not None
                tenant.rename("After")
                await repository.save(tenant)

        rows = await _audit_rows_for(admin_engine, tenant_id)
        row = rows[0]

        assert row["action"] == "update"
        assert row["entity_name"] == "tenant"
        assert row["tenant_id"] == tenant_id
        assert row["actor_id"] == actor_id
        assert row["before_state"]["name"] == "Before"  # type: ignore[index]
        assert row["after_state"]["name"] == "After"  # type: ignore[index]

    async def test_unmodified_columns_are_not_in_before_state(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        """Only what changed — `before_state` is a diff, not a full snapshot."""
        tenant_id = await _seed_tenant(admin_engine, name="Only Name Changes")
        context = RequestTenantContext(tenant_id=tenant_id)

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repository = SqlAlchemyTenantRepository(uow)
                tenant = await repository.get(tenant_id)
                assert tenant is not None
                tenant.rename("Only Name Changed")
                await repository.save(tenant)

        rows = await _audit_rows_for(admin_engine, tenant_id)
        before_state = rows[0]["before_state"]
        assert "name" in before_state  # type: ignore[operator]
        assert "slug" not in before_state  # type: ignore[operator]

    async def test_a_read_only_transaction_produces_no_audit_row(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine, name="Never Modified")
        context = RequestTenantContext(tenant_id=tenant_id)

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repository = SqlAlchemyTenantRepository(uow)
                await repository.get(tenant_id)
                # No mutation — nothing to audit.

        rows = await _audit_rows_for(admin_engine, tenant_id)
        assert rows == []

    async def test_a_rolled_back_transaction_produces_no_audit_row(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine, name="Rolled Back")
        context = RequestTenantContext(tenant_id=tenant_id)

        async for session in database.open_session(tenant_id=tenant_id):
            uow = SqlAlchemyUnitOfWork(session, context)
            repository = SqlAlchemyTenantRepository(uow)
            tenant = await repository.get(tenant_id)
            assert tenant is not None
            tenant.rename("Should Not Persist")
            await repository.save(tenant)
            await uow.rollback()

        rows = await _audit_rows_for(admin_engine, tenant_id)
        assert rows == []


class TestImmutability:
    """Immutability is enforced by the database, not application discipline
    (`06-database-architecture.md` §6) — the application role has no
    UPDATE/DELETE privilege on audit.audit_log at all."""

    async def test_application_role_cannot_update_audit_rows(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine, name="Immutability Target")
        context = RequestTenantContext(tenant_id=tenant_id)

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repository = SqlAlchemyTenantRepository(uow)
                tenant = await repository.get(tenant_id)
                assert tenant is not None
                tenant.rename("Triggers An Audit Row")
                await repository.save(tenant)

        async for session in database.open_session(tenant_id=tenant_id):
            with pytest.raises(DBAPIError, match="permission denied"):
                await session.execute(
                    text("UPDATE audit.audit_log SET action = 'tampered' WHERE tenant_id = :t"),
                    {"t": str(tenant_id)},
                )

    async def test_application_role_cannot_delete_audit_rows(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine, name="Delete Immutability Target")
        context = RequestTenantContext(tenant_id=tenant_id)

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repository = SqlAlchemyTenantRepository(uow)
                tenant = await repository.get(tenant_id)
                assert tenant is not None
                tenant.rename("Triggers Another Audit Row")
                await repository.save(tenant)

        async for session in database.open_session(tenant_id=tenant_id):
            with pytest.raises(DBAPIError, match="permission denied"):
                await session.execute(
                    text("DELETE FROM audit.audit_log WHERE tenant_id = :t"), {"t": str(tenant_id)}
                )
