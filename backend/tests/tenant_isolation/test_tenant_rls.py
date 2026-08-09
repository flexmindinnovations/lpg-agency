"""Tenant isolation, enforced by PostgreSQL Row-Level Security — not by
application filters.

Per `03-backend-architecture.md` §12.1, this is a **dedicated** suite,
distinct from `tests/unit/` and `tests/integration/`: "BR-30 is the
highest-severity failure mode in the system." Every query here runs as the
real, non-superuser `lpg_app` role, using **raw SQL directly** rather than
the repository — proving the database-level backstop holds even when
application code is bypassed entirely (`06-database-architecture.md` §2:
"protects raw SQL, reporting queries, ad-hoc analysis... automatically").

Seed data is created via the elevated `lpg_admin` role (RLS makes
self-registration through `lpg_app` impossible by design — see migration
`0242df1a3871`), which doubles as this suite's proof that the two tenants
genuinely exist and are genuinely distinct rows, not an artifact of a query
that would have returned nothing regardless.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, cast

import pytest
from sqlalchemy import text

from lpg.infrastructure.persistence.database import Database

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy import TextClause
    from sqlalchemy.engine import CursorResult
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

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
                {"name": name, "slug": f"rls-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
    return uuid.UUID(str(tenant_id))


async def _row_exists(admin_engine: AsyncEngine, tenant_id: uuid.UUID) -> bool:
    async with admin_engine.connect() as conn:
        return bool(
            (
                await conn.execute(
                    text("SELECT 1 FROM tenant.tenant WHERE id = :id"), {"id": str(tenant_id)}
                )
            ).first()
        )


async def _row_name(admin_engine: AsyncEngine, tenant_id: uuid.UUID) -> str:
    async with admin_engine.connect() as conn:
        name = (
            await conn.execute(
                text("SELECT name FROM tenant.tenant WHERE id = :id"), {"id": str(tenant_id)}
            )
        ).scalar_one()
    return str(name)


async def _rowcount(session: AsyncSession, statement: TextClause, params: dict[str, str]) -> int:
    """`.execute()`'s declared return type is the generic `Result[Any]`,
    which doesn't statically expose `.rowcount` — that's a `CursorResult`
    -specific attribute, real at runtime for the UPDATE/DELETE statements
    this suite issues, just not part of the base `Result` stub. One cast
    here instead of five scattered across the test bodies.
    """
    result = await session.execute(statement, params)
    return cast("CursorResult[Any]", result).rowcount


@pytest.fixture
async def two_tenants(admin_engine: AsyncEngine) -> tuple[uuid.UUID, uuid.UUID]:
    """Tenant A and Tenant B, seeded via the elevated role."""
    tenant_a = await _seed_tenant(admin_engine, name="Tenant A (RLS proof)")
    tenant_b = await _seed_tenant(admin_engine, name="Tenant B (RLS proof)")
    return tenant_a, tenant_b


class TestTenantACannotReadTenantB:
    async def test_direct_lookup_by_id_returns_nothing(
        self, database: Database, two_tenants: tuple[uuid.UUID, uuid.UUID]
    ) -> None:
        tenant_a, tenant_b = two_tenants

        async for session in database.open_session(tenant_id=tenant_a):
            result = await session.execute(
                text("SELECT id FROM tenant.tenant WHERE id = :id"), {"id": str(tenant_b)}
            )
            assert result.first() is None

    async def test_unfiltered_select_only_returns_the_caller_s_own_row(
        self, database: Database, two_tenants: tuple[uuid.UUID, uuid.UUID]
    ) -> None:
        tenant_a, tenant_b = two_tenants

        async for session in database.open_session(tenant_id=tenant_a):
            rows = (await session.execute(text("SELECT id FROM tenant.tenant"))).scalars().all()
            visible_ids = set(rows)

            assert tenant_a in visible_ids
            assert tenant_b not in visible_ids
            # Not "coincidentally filtered to one row" — exactly the caller's own.
            assert visible_ids == {tenant_a}


class TestTenantACannotModifyTenantB:
    async def test_update_by_id_affects_zero_rows(
        self,
        database: Database,
        two_tenants: tuple[uuid.UUID, uuid.UUID],
        admin_engine: AsyncEngine,
    ) -> None:
        tenant_a, tenant_b = two_tenants

        async for session in database.open_session(tenant_id=tenant_a):
            rowcount = await _rowcount(
                session,
                text("UPDATE tenant.tenant SET name = 'Hijacked by A' WHERE id = :id"),
                {"id": str(tenant_b)},
            )
            assert rowcount == 0
            await session.commit()

        # The database-level proof, not an application-layer inference:
        # Tenant B's row is byte-for-byte unchanged.
        assert await _row_name(admin_engine, tenant_b) == "Tenant B (RLS proof)"

    async def test_positive_control_update_of_own_row_succeeds(
        self,
        database: Database,
        two_tenants: tuple[uuid.UUID, uuid.UUID],
        admin_engine: AsyncEngine,
    ) -> None:
        """Proves the negative results above are RLS filtering, not a
        malformed query, a missing privilege, or a broken connection."""
        tenant_a, _tenant_b = two_tenants

        async for session in database.open_session(tenant_id=tenant_a):
            rowcount = await _rowcount(
                session,
                text("UPDATE tenant.tenant SET name = 'Renamed by A (own row)' WHERE id = :id"),
                {"id": str(tenant_a)},
            )
            assert rowcount == 1
            await session.commit()

        assert await _row_name(admin_engine, tenant_a) == "Renamed by A (own row)"


class TestTenantACannotDeleteTenantB:
    async def test_delete_by_id_affects_zero_rows(
        self,
        database: Database,
        two_tenants: tuple[uuid.UUID, uuid.UUID],
        admin_engine: AsyncEngine,
    ) -> None:
        tenant_a, tenant_b = two_tenants

        async for session in database.open_session(tenant_id=tenant_a):
            rowcount = await _rowcount(
                session, text("DELETE FROM tenant.tenant WHERE id = :id"), {"id": str(tenant_b)}
            )
            assert rowcount == 0
            await session.commit()

        assert await _row_exists(admin_engine, tenant_b) is True

    async def test_positive_control_delete_of_own_row_succeeds(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        """A dedicated third tenant, deleted only by itself — proves DELETE
        mechanically works under RLS when the row genuinely belongs to the
        caller, so the zero-rowcount result above is RLS-specific, not
        "DELETE never works for this role."""
        deletable = await _seed_tenant(admin_engine, name="Tenant C (delete-own proof)")

        async for session in database.open_session(tenant_id=deletable):
            rowcount = await _rowcount(
                session, text("DELETE FROM tenant.tenant WHERE id = :id"), {"id": str(deletable)}
            )
            assert rowcount == 1
            await session.commit()

        assert await _row_exists(admin_engine, deletable) is False


class TestBothDirections:
    """The isolation must hold symmetrically — B is equally blocked from A."""

    async def test_tenant_b_cannot_read_or_modify_tenant_a(
        self,
        database: Database,
        two_tenants: tuple[uuid.UUID, uuid.UUID],
        admin_engine: AsyncEngine,
    ) -> None:
        tenant_a, tenant_b = two_tenants

        async for session in database.open_session(tenant_id=tenant_b):
            read = await session.execute(
                text("SELECT id FROM tenant.tenant WHERE id = :id"), {"id": str(tenant_a)}
            )
            assert read.first() is None

            rowcount = await _rowcount(
                session,
                text("UPDATE tenant.tenant SET name = 'Hijacked by B' WHERE id = :id"),
                {"id": str(tenant_a)},
            )
            assert rowcount == 0
            await session.commit()

        original_or_prior_rename = await _row_name(admin_engine, tenant_a)
        assert original_or_prior_rename != "Hijacked by B"


class TestNoTenantContextFailsClosed:
    """The backstop's default state: no session variable set → no rows,
    never an error and never every row (`06-database-architecture.md` §2.1)."""

    async def test_unscoped_session_sees_no_rows_at_all(
        self, database: Database, two_tenants: tuple[uuid.UUID, uuid.UUID]
    ) -> None:
        two_tenants  # noqa: B018 - ensures the seed data exists for this assertion to be meaningful

        async for session in database.open_session():  # no tenant_id
            rows = (await session.execute(text("SELECT id FROM tenant.tenant"))).scalars().all()
            assert rows == []
