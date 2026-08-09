"""`RenameTenantUseCase` end to end, against a real PostgreSQL.

The full seam Phase 2's CQRS/domain-event instructions ask for one example
of: Command → Application Service → Repository → Unit of Work → domain
event, dispatched post-commit.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from lpg.application.common.errors import NotFoundError
from lpg.application.common.tenant import RequestTenantContext
from lpg.application.tenant.rename_tenant import RenameTenantCommand, RenameTenantUseCase
from lpg.domain.tenant.tenant import TenantRenamed
from lpg.infrastructure.events.dispatcher import DomainEventDispatcher
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.repositories.tenant import SqlAlchemyTenantRepository
from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.config.settings import Settings
    from lpg.domain.common.base import DomainEvent

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


async def _seed_tenant(admin_engine: AsyncEngine, *, name: str, slug: str) -> uuid.UUID:
    async with admin_engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug) "
                    "VALUES (gen_random_uuid(), :name, :slug) "
                    "RETURNING id"
                ),
                {"name": name, "slug": slug},
            )
        ).scalar_one()
    # asyncpg already returns a real uuid.UUID for a `uuid` column; the
    # explicit conversion is only to satisfy mypy --strict against Core's
    # `Any`-typed raw-SQL result, not a runtime no-op.
    return uuid.UUID(str(tenant_id))


class TestRenameTenantUseCase:
    async def test_renames_and_persists(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(
            admin_engine, name="Original Name", slug=f"use-case-{uuid.uuid4().hex[:8]}"
        )
        context = RequestTenantContext(tenant_id=tenant_id)

        async for session in database.open_session(tenant_id=tenant_id):
            uow = SqlAlchemyUnitOfWork(session, context)
            use_case = RenameTenantUseCase(SqlAlchemyTenantRepository(uow), uow)

            await use_case.execute(RenameTenantCommand(tenant_id=tenant_id, new_name="New Name"))

        async for verify_session in database.open_session(tenant_id=tenant_id):
            verify_uow = SqlAlchemyUnitOfWork(verify_session, context)
            reloaded = await SqlAlchemyTenantRepository(verify_uow).get(tenant_id)
            assert reloaded is not None
            assert reloaded.name == "New Name"

    async def test_dispatches_the_domain_event_after_commit(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(
            admin_engine, name="Event Co", slug=f"event-{uuid.uuid4().hex[:8]}"
        )
        context = RequestTenantContext(tenant_id=tenant_id)

        dispatcher = DomainEventDispatcher()
        received: list[DomainEvent] = []

        async def handler(event: DomainEvent) -> None:
            received.append(event)

        dispatcher.register(TenantRenamed, handler)

        async for session in database.open_session(tenant_id=tenant_id):
            uow = SqlAlchemyUnitOfWork(session, context, event_dispatcher=dispatcher)
            use_case = RenameTenantUseCase(SqlAlchemyTenantRepository(uow), uow)

            await use_case.execute(
                RenameTenantCommand(tenant_id=tenant_id, new_name="Renamed For Event")
            )

        assert len(received) == 1
        event = received[0]
        assert isinstance(event, TenantRenamed)
        assert event.tenant_id == tenant_id
        assert event.new_name == "Renamed For Event"

    async def test_raises_not_found_for_a_tenant_outside_rls_visibility(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        """The use case's `NotFoundError` and "not visible to another
        tenant" collapse into the same response deliberately — see
        `lpg.application.common.errors.NotFoundError`'s own docstring on why
        a 403-vs-404 distinction would leak cross-tenant existence."""
        acting_tenant = await _seed_tenant(
            admin_engine, name="Acting Co", slug=f"acting-{uuid.uuid4().hex[:8]}"
        )
        other_tenant = await _seed_tenant(
            admin_engine, name="Invisible Co", slug=f"invisible-{uuid.uuid4().hex[:8]}"
        )
        context = RequestTenantContext(tenant_id=acting_tenant)

        async for session in database.open_session(tenant_id=acting_tenant):
            uow = SqlAlchemyUnitOfWork(session, context)
            use_case = RenameTenantUseCase(SqlAlchemyTenantRepository(uow), uow)

            with pytest.raises(NotFoundError):
                await use_case.execute(
                    RenameTenantCommand(tenant_id=other_tenant, new_name="Should Not Apply")
                )

    async def test_rejects_an_empty_name(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        from lpg.domain.common.base import InvariantViolation

        tenant_id = await _seed_tenant(
            admin_engine, name="Guarded Co", slug=f"guarded-{uuid.uuid4().hex[:8]}"
        )
        context = RequestTenantContext(tenant_id=tenant_id)

        async for session in database.open_session(tenant_id=tenant_id):
            uow = SqlAlchemyUnitOfWork(session, context)
            use_case = RenameTenantUseCase(SqlAlchemyTenantRepository(uow), uow)

            with pytest.raises(InvariantViolation):
                await use_case.execute(RenameTenantCommand(tenant_id=tenant_id, new_name="   "))
