"""Integration tests for `SqlAlchemyReferenceNumberSequence`
(`platform.reference_number_sequence`), the shared, tenant-scoped counter
backing every module's human-readable reference number (`INV-2026-000001`,
`ORD000001`, `EMP0001`, ...) introduced by the
`f3a7c2e8d4b1`/`b8d4f1a9c6e3` migrations.

Mirrors `test_customer_repository.py`'s `database`/`_seed_tenant` fixtures —
real Postgres, no mocks, since the whole point of this sequence is the
`INSERT ... ON CONFLICT ... DO UPDATE ... RETURNING` upsert's concurrency
behavior, which a mock can't exercise.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from lpg.application.common.tenant import RequestTenantContext
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.repositories.reference_number import (
    SqlAlchemyReferenceNumberSequence,
)
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
                    "VALUES (gen_random_uuid(), 'Reference Number Test Co', :slug, "
                    "'ops@example.com') RETURNING id"
                ),
                {"slug": f"refnum-test-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
    return uuid.UUID(str(tenant_id))


class TestSqlAlchemyReferenceNumberSequence:
    async def test_sequential_calls_increment_without_gaps(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        context = RequestTenantContext(tenant_id=tenant_id)

        numbers: list[str] = []
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                sequence = SqlAlchemyReferenceNumberSequence(
                    uow, tenant_id, entity_type="order", prefix="ORD"
                )
                for _ in range(3):
                    numbers.append(await sequence.next())
                await uow.commit()

        assert numbers == ["ORD000001", "ORD000002", "ORD000003"]

    async def test_include_year_formats_with_current_year_prefix(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        context = RequestTenantContext(tenant_id=tenant_id)

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                sequence = SqlAlchemyReferenceNumberSequence(
                    uow, tenant_id, entity_type="invoice", prefix="INV", include_year=True
                )
                number = await sequence.next()
                await uow.commit()

        import datetime

        year = datetime.datetime.now(datetime.UTC).year
        assert number == f"INV-{year}-000001"

    async def test_different_entity_types_do_not_interfere(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        """Two modules for the same tenant each get their own counter,
        keyed on `(tenant_id, entity_type)` — an order and a complaint
        created back-to-back both get "...000001", not "000001"/"000002".
        """
        tenant_id = await _seed_tenant(admin_engine)
        context = RequestTenantContext(tenant_id=tenant_id)

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                order_sequence = SqlAlchemyReferenceNumberSequence(
                    uow, tenant_id, entity_type="order", prefix="ORD"
                )
                complaint_sequence = SqlAlchemyReferenceNumberSequence(
                    uow, tenant_id, entity_type="complaint", prefix="CMP"
                )
                order_number = await order_sequence.next()
                complaint_number = await complaint_sequence.next()
                await uow.commit()

        assert order_number == "ORD000001"
        assert complaint_number == "CMP000001"

    async def test_concurrent_calls_for_the_same_tenant_and_entity_type_never_collide(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        """The `ON CONFLICT ... DO UPDATE ... RETURNING` upsert relies on
        Postgres's row-level lock on the `(tenant_id, entity_type)` row to
        serialize concurrent callers — this is the actual mechanic under
        test, not achievable with a mocked repository.
        """
        tenant_id = await _seed_tenant(admin_engine)
        context = RequestTenantContext(tenant_id=tenant_id)

        async def _next_number() -> str:
            async for session in database.open_session(tenant_id=tenant_id):
                async with SqlAlchemyUnitOfWork(session, context) as uow:
                    sequence = SqlAlchemyReferenceNumberSequence(
                        uow, tenant_id, entity_type="order", prefix="ORD"
                    )
                    number = await sequence.next()
                    await uow.commit()
                    return number
            msg = "database.open_session yielded no session"
            raise RuntimeError(msg)

        results = await asyncio.gather(*(_next_number() for _ in range(10)))

        assert len(results) == len(set(results)), f"collision among concurrent calls: {results}"
        assert sorted(results) == [f"ORD{i:06d}" for i in range(1, 11)]
