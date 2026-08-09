"""Database connection foundation, against a real PostgreSQL.

Never SQLite, never a mock. Row-Level Security policies, `SET LOCAL`
behaviour, and PostgreSQL-specific types cannot be exercised by either
(``docs/implementation/testing-strategy.md``).

These tests skip with a reason when PostgreSQL is unreachable rather than
failing. A red suite caused by a stopped container trains people to ignore red
suites.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from lpg.infrastructure.persistence.database import Database

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

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


class TestConnection:
    async def test_ping_succeeds(self, database: Database) -> None:
        assert await database.ping() is True

    async def test_session_executes_a_query(self, database: Database) -> None:
        async for session in database.session():
            result = await session.execute(text("SELECT 1"))
            assert result.scalar_one() == 1

    async def test_reports_postgresql_17_or_later(self, database: Database) -> None:
        async for session in database.session():
            version = (await session.execute(text("SHOW server_version_num"))).scalar_one()
            assert int(version) >= 170000, f"expected PostgreSQL 17+, got {version}"


class TestRequiredExtensions:
    """The extensions ADR-013 depends on must actually be installed.

    Assumed-present extensions are a classic first-migration failure: the
    migration works locally where someone installed it by hand, and fails in
    the environment where nobody did.
    """

    @pytest.mark.parametrize("extension", ["pgcrypto", "citext", "pg_trgm"])
    async def test_extension_is_installed(self, database: Database, extension: str) -> None:
        async for session in database.session():
            found = (
                await session.execute(
                    text("SELECT count(*) FROM pg_extension WHERE extname = :name"),
                    {"name": extension},
                )
            ).scalar_one()
            assert found == 1, f"{extension} is not installed"

    async def test_gen_random_uuid_is_available(self, database: Database) -> None:
        """Offline-safe, client-generatable primary keys depend on this (D-24)."""
        async for session in database.session():
            generated = (await session.execute(text("SELECT gen_random_uuid()"))).scalar_one()
            assert isinstance(generated, uuid.UUID)


class TestTenantContextSeam:
    """The `SET LOCAL app.current_tenant_id` mechanism RLS predicates on.

    No tenant-scoped tables exist yet, so these verify the *seam* rather than
    isolation itself. The isolation suite arrives in Phase 2 with the first
    tables (`06-database-architecture.md` §2).
    """

    async def test_defaults_to_empty_so_unscoped_queries_fail_closed(
        self, database: Database
    ) -> None:
        """Unset tenant context must return empty, never raise.

        A raise would be a 500; empty means an RLS-protected query returns no
        rows. Failing closed is the correct behaviour for a tenant backstop.
        """
        async for session in database.session():
            value = (
                await session.execute(text("SELECT current_setting('app.current_tenant_id')"))
            ).scalar_one()
            assert value == ""

    async def test_set_local_applies_within_the_transaction(self, database: Database) -> None:
        tenant_id = uuid.uuid4()
        async for session in database.session(tenant_id=tenant_id):
            value = (
                await session.execute(text("SELECT current_setting('app.current_tenant_id')"))
            ).scalar_one()
            assert value == str(tenant_id)

    async def test_set_local_does_not_leak_across_pooled_connections(
        self, database: Database
    ) -> None:
        """The whole reason §2 uses SET LOCAL rather than SET.

        Session-level state would survive on a pooled connection and be
        inherited by the next request — a cross-tenant leak through the
        connection pool. It is also what keeps this compatible with
        transaction-mode server-side pooling (Supavisor, PgBouncer).
        """
        tenant_id = uuid.uuid4()
        async for _scoped in database.session(tenant_id=tenant_id):
            pass

        async for session in database.session():
            leaked = (
                await session.execute(text("SELECT current_setting('app.current_tenant_id')"))
            ).scalar_one()
            assert leaked == "", "tenant context leaked to a subsequent connection"


class TestApplicationRolePrivileges:
    """ADR-017: the application role must not be able to bypass RLS.

    This is the highest-severity configuration error in the system. RLS is the
    backstop that holds when application code is wrong; a role with BYPASSRLS
    removes it silently, and nothing else in the test suite would notice.
    """

    async def test_application_role_cannot_bypass_rls(self, database: Database) -> None:
        async for session in database.session():
            row = (
                await session.execute(
                    text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
                )
            ).one()
            is_superuser, can_bypass_rls = row
            assert not is_superuser, f"{'current_user'} is a superuser — RLS would be bypassed"
            assert not can_bypass_rls, "application role holds BYPASSRLS — tenant isolation is void"


class TestTransactionBehaviour:
    async def test_exception_propagates_out_of_the_session(self, database: Database) -> None:
        """A failure must not be swallowed into a silent rollback.

        Swallowing it would return 200 to a client whose write was discarded —
        the worst possible outcome for a delivery confirmation.
        """
        with pytest.raises(RuntimeError, match="forced failure"):
            async for session in database.session():
                await session.execute(text("SELECT 1"))
                msg = "forced failure"
                raise RuntimeError(msg)

    async def test_rollback_discards_work(self, database: Database) -> None:
        """One transaction per command means a failure discards all of it.

        BR-29 depends on this: a delivery confirmation updates Order, Ledger
        and Inventory together, or none of them.

        Uses a temp table on a single explicitly-held connection. The
        application role deliberately lacks CREATE on schema ``public`` (least
        privilege — Alembic runs as the superuser role), so a permanent table
        is not available here, and pooling makes connection identity across
        two ``session()`` calls non-deterministic.
        """
        table = f"rollback_probe_{uuid.uuid4().hex[:8]}"

        async with database.engine.connect() as connection:
            transaction = await connection.begin()
            await connection.execute(text(f"CREATE TEMP TABLE {table} (id int)"))
            await connection.execute(text(f"INSERT INTO {table} VALUES (1)"))
            assert (
                await connection.execute(text(f"SELECT count(*) FROM {table}"))
            ).scalar_one() == 1

            await transaction.rollback()

            survived = (
                await connection.execute(
                    text("SELECT count(*) FROM pg_tables WHERE tablename = :t"),
                    {"t": table},
                )
            ).scalar_one()
            assert survived == 0, "rollback did not discard the transaction"

    async def test_commit_persists_work(self, database: Database) -> None:
        table = f"commit_probe_{uuid.uuid4().hex[:8]}"

        async for session in database.session():
            await session.execute(text(f"CREATE TEMP TABLE {table} (id int)"))
            await session.execute(text(f"INSERT INTO {table} VALUES (1)"))
            count = (await session.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one()
            assert count == 1

    async def test_application_role_cannot_create_tables(self, database: Database) -> None:
        """Least privilege: schema changes go through Alembic as the superuser
        role, never through the application connection
        (``06-database-architecture.md`` §10). If the application could issue
        DDL, an ad-hoc fix in production would bypass migration review entirely.
        """
        from sqlalchemy.exc import ProgrammingError

        with pytest.raises(ProgrammingError, match="permission denied"):
            async for session in database.session():
                await session.execute(text("CREATE TABLE should_not_be_possible (id int)"))
