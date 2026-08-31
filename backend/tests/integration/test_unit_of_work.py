"""``SqlAlchemyUnitOfWork``, against a real PostgreSQL.

Placed under ``tests/integration/`` (not the ``tests/infrastructure/`` path
named in ``03-backend-architecture.md`` §14's aspirational folder structure)
to match this repository's actual, established convention — a real/mock
distinction (``unit`` vs ``integration``), not a layer distinction. Phase 1
set this precedent; Phase 2 follows it rather than introducing a second,
parallel test-folder taxonomy the moment a plausible motivation appears.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from lpg.application.common.tenant import RequestTenantContext
from lpg.domain.common.base import AggregateRoot, DomainEvent
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration


@dataclass(frozen=True, slots=True)
class _ProbeEvent(DomainEvent):
    """A minimal concrete event — `DomainEvent` itself carries no payload."""

    label: str = ""


class _ProbeAggregate(AggregateRoot):
    """A minimal aggregate, just enough to record and expose events."""

    def touch(self, label: str) -> None:
        self.record_event(_ProbeEvent(label=label))


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


@pytest.fixture
def tenant_context() -> RequestTenantContext:
    return RequestTenantContext(tenant_id=uuid.uuid4())


class TestCommit:
    async def test_commit_persists_work(
        self, database: Database, tenant_context: RequestTenantContext
    ) -> None:
        table = f"uow_commit_probe_{uuid.uuid4().hex[:8]}"

        async for session in database.open_session(tenant_id=tenant_context.tenant_id):
            uow = SqlAlchemyUnitOfWork(session, tenant_context)
            await session.execute(text(f"CREATE TEMP TABLE {table} (id int)"))
            await session.execute(text(f"INSERT INTO {table} VALUES (1)"))
            await uow.commit()

            count = (await session.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one()
            assert count == 1

    async def test_commit_is_idempotent(
        self, database: Database, tenant_context: RequestTenantContext
    ) -> None:
        """A second `commit()` call must not raise or double-apply."""
        async for session in database.open_session(tenant_id=tenant_context.tenant_id):
            uow = SqlAlchemyUnitOfWork(session, tenant_context)
            await uow.commit()
            await uow.commit()  # must not raise

    async def test_context_manager_commits_on_clean_exit(
        self, database: Database, tenant_context: RequestTenantContext
    ) -> None:
        table = f"uow_ctx_commit_probe_{uuid.uuid4().hex[:8]}"

        async for session in database.open_session(tenant_id=tenant_context.tenant_id):
            async with SqlAlchemyUnitOfWork(session, tenant_context):
                await session.execute(text(f"CREATE TEMP TABLE {table} (id int)"))
                await session.execute(text(f"INSERT INTO {table} VALUES (1)"))

            count = (await session.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one()
            assert count == 1

    async def test_explicit_commit_then_context_exit_does_not_double_commit(
        self, database: Database, tenant_context: RequestTenantContext
    ) -> None:
        """A use case that calls `uow.commit()` explicitly, inside `async
        with`, must not trigger a second commit attempt on clean exit."""
        async for session in database.open_session(tenant_id=tenant_context.tenant_id):
            async with SqlAlchemyUnitOfWork(session, tenant_context) as uow:
                await uow.commit()
                # If __aexit__ tried to commit again on an already-finished
                # UoW, this would be the point a stale-session error surfaces.


class TestRollback:
    async def test_rollback_discards_work(
        self, database: Database, tenant_context: RequestTenantContext
    ) -> None:
        table = f"uow_rollback_probe_{uuid.uuid4().hex[:8]}"

        async for session in database.open_session(tenant_id=tenant_context.tenant_id):
            uow = SqlAlchemyUnitOfWork(session, tenant_context)
            await session.execute(text(f"CREATE TEMP TABLE {table} (id int)"))
            await session.execute(text(f"INSERT INTO {table} VALUES (1)"))
            await uow.rollback()

            # The temp table itself was rolled back out of existence — querying
            # it now would fail. Assert against pg_tables instead, on a fresh
            # implicit transaction.
            survived = (
                await session.execute(
                    text("SELECT count(*) FROM pg_tables WHERE tablename = :t"), {"t": table}
                )
            ).scalar_one()
            assert survived == 0

    async def test_context_manager_rolls_back_on_exception(
        self, database: Database, tenant_context: RequestTenantContext
    ) -> None:
        table = f"uow_ctx_rollback_probe_{uuid.uuid4().hex[:8]}"

        with pytest.raises(RuntimeError, match="forced failure"):
            async for session in database.open_session(tenant_id=tenant_context.tenant_id):
                async with SqlAlchemyUnitOfWork(session, tenant_context):
                    await session.execute(text(f"CREATE TEMP TABLE {table} (id int)"))
                    msg = "forced failure"
                    raise RuntimeError(msg)

    async def test_rollback_is_idempotent(
        self, database: Database, tenant_context: RequestTenantContext
    ) -> None:
        async for session in database.open_session(tenant_id=tenant_context.tenant_id):
            uow = SqlAlchemyUnitOfWork(session, tenant_context)
            await uow.rollback()
            await uow.rollback()  # must not raise

    async def test_rollback_then_context_exit_does_not_attempt_a_commit(
        self, database: Database, tenant_context: RequestTenantContext
    ) -> None:
        async for session in database.open_session(tenant_id=tenant_context.tenant_id):
            async with SqlAlchemyUnitOfWork(session, tenant_context) as uow:
                await uow.rollback()
                # Clean exit after an explicit rollback must stay a rollback,
                # never flip to a commit.


class TestEventCollection:
    async def test_collect_events_returns_nothing_when_no_aggregate_is_touched(
        self, database: Database, tenant_context: RequestTenantContext
    ) -> None:
        async for session in database.open_session(tenant_id=tenant_context.tenant_id):
            uow = SqlAlchemyUnitOfWork(session, tenant_context)
            assert uow.collect_events() == ()

    async def test_collect_events_gathers_from_every_registered_aggregate(
        self, database: Database, tenant_context: RequestTenantContext
    ) -> None:
        async for session in database.open_session(tenant_id=tenant_context.tenant_id):
            uow = SqlAlchemyUnitOfWork(session, tenant_context)

            first = _ProbeAggregate(uuid.uuid4())
            first.touch("first")
            second = _ProbeAggregate(uuid.uuid4())
            second.touch("second-a")
            second.touch("second-b")

            uow.register_aggregate(first)
            uow.register_aggregate(second)

            events = uow.collect_events()
            assert len(events) == 3
            assert {event.label for event in events if isinstance(event, _ProbeEvent)} == {
                "first",
                "second-a",
                "second-b",
            }

    async def test_untouched_aggregates_do_not_leak_into_collection(
        self, database: Database, tenant_context: RequestTenantContext
    ) -> None:
        async for session in database.open_session(tenant_id=tenant_context.tenant_id):
            uow = SqlAlchemyUnitOfWork(session, tenant_context)

            registered = _ProbeAggregate(uuid.uuid4())
            registered.touch("registered")
            not_registered = _ProbeAggregate(uuid.uuid4())
            not_registered.touch("not-registered")

            uow.register_aggregate(registered)
            # `not_registered` is deliberately never passed to register_aggregate.

            events = uow.collect_events()
            assert len(events) == 1

    async def test_registering_the_same_aggregate_twice_does_not_double_events(
        self, database: Database, tenant_context: RequestTenantContext
    ) -> None:
        # A use case that loads an aggregate (get_by_id registers it) then
        # saves it (registers again) must not have its events dispatched
        # twice.
        async for session in database.open_session(tenant_id=tenant_context.tenant_id):
            uow = SqlAlchemyUnitOfWork(session, tenant_context)

            aggregate = _ProbeAggregate(uuid.uuid4())
            aggregate.touch("only-once")

            uow.register_aggregate(aggregate)
            uow.register_aggregate(aggregate)

            assert len(uow.collect_events()) == 1


class TestSessionExposure:
    async def test_session_property_is_the_scoped_session(
        self, database: Database, tenant_context: RequestTenantContext
    ) -> None:
        async for session in database.open_session(tenant_id=tenant_context.tenant_id):
            uow = SqlAlchemyUnitOfWork(session, tenant_context)
            assert uow.session is session

            value = (
                await uow.session.execute(text("SELECT current_setting('app.current_tenant_id')"))
            ).scalar_one()
            assert value == str(tenant_context.tenant_id)
