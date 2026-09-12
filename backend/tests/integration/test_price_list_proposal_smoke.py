"""`tenant.price_list_proposal` against a real Postgres session — the OMC
rate-review pipeline (AI Operational Intelligence, Horizon 1 Stage 3).

What is real: a seeded tenant/branch/cylinder_type, a pending proposal row
inserted directly (the monthly fetch job's own write path is exercised by
`test_pricing_jobs_smoke.py`; this file's concern is the staff review
step that consumes one), and the accept/reject use cases running against
that row through a real RLS-scoped session.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration

_ADMIN_URL = "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:5433/lpg_test"


async def _seed_pending_proposal(engine: AsyncEngine) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """tenant -> branch -> cylinder_type, plus one pending
    `price_list_proposal` row. Returns `(tenant_id, cylinder_type_id,
    proposal_id)`."""
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'Proposal Smoke', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"proposal-smoke-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
        cylinder_type_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.cylinder_type (id, tenant_id, name, weight_kg) "
                    "VALUES (gen_random_uuid(), :t, '14.2kg Domestic', 14.2) RETURNING id"
                ),
                {"t": str(tenant_id)},
            )
        ).scalar_one()
        effective_from = datetime.now(UTC) + timedelta(days=20)
        proposal_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.price_list_proposal "
                    "(id, tenant_id, cylinder_type_id, customer_type, proposed_price, "
                    "effective_from, source_url, fetched_at) "
                    "VALUES (gen_random_uuid(), :t, :ct, 'domestic', 960.00, :ef, "
                    "'https://example.com/rates', now()) RETURNING id"
                ),
                {"t": str(tenant_id), "ct": str(cylinder_type_id), "ef": effective_from},
            )
        ).scalar_one()
    return (
        uuid.UUID(str(tenant_id)),
        uuid.UUID(str(cylinder_type_id)),
        uuid.UUID(str(proposal_id)),
    )


async def _accept(
    integration_settings: Settings, *, tenant_id: uuid.UUID, proposal_id: uuid.UUID
) -> Decimal:
    from lpg.application.common.tenant import RequestTenantContext
    from lpg.application.tenant.price_list_proposal import (
        AcceptPriceListProposalCommand,
        AcceptPriceListProposalUseCase,
    )
    from lpg.infrastructure.persistence.database import build_database
    from lpg.infrastructure.persistence.repositories.tenant import (
        SqlAlchemyPriceListProposalRepository,
        SqlAlchemyPriceListRepository,
    )
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    database = build_database(integration_settings)
    database.connect()
    try:
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(
                session, RequestTenantContext(tenant_id=tenant_id)
            ) as uow:
                proposal_repo = SqlAlchemyPriceListProposalRepository(uow)
                price_list_repo = SqlAlchemyPriceListRepository(uow)
                use_case = AcceptPriceListProposalUseCase(proposal_repo, price_list_repo, uow)
                entry = await use_case.execute(
                    AcceptPriceListProposalCommand(
                        proposal_id=proposal_id, reviewed_by=uuid.uuid4()
                    )
                )
                return entry.price
        msg = "no session yielded"
        raise AssertionError(msg)
    finally:
        await database.disconnect()


async def _reject(
    integration_settings: Settings, *, tenant_id: uuid.UUID, proposal_id: uuid.UUID
) -> None:
    from lpg.application.common.tenant import RequestTenantContext
    from lpg.application.tenant.price_list_proposal import (
        RejectPriceListProposalCommand,
        RejectPriceListProposalUseCase,
    )
    from lpg.infrastructure.persistence.database import build_database
    from lpg.infrastructure.persistence.repositories.tenant import (
        SqlAlchemyPriceListProposalRepository,
    )
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    database = build_database(integration_settings)
    database.connect()
    try:
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(
                session, RequestTenantContext(tenant_id=tenant_id)
            ) as uow:
                proposal_repo = SqlAlchemyPriceListProposalRepository(uow)
                await RejectPriceListProposalUseCase(proposal_repo, uow).execute(
                    RejectPriceListProposalCommand(
                        proposal_id=proposal_id, reviewed_by=uuid.uuid4()
                    )
                )
    finally:
        await database.disconnect()


async def _cleanup(engine: AsyncEngine, *, tenant_id: uuid.UUID) -> None:
    async with engine.begin() as conn:
        for stmt in (
            "DELETE FROM tenant.price_list WHERE tenant_id = :t",
            "DELETE FROM tenant.price_list_proposal WHERE tenant_id = :t",
            "DELETE FROM tenant.cylinder_type WHERE tenant_id = :t",
            "DELETE FROM tenant.tenant WHERE id = :t",
        ):
            await conn.execute(text(stmt), {"t": str(tenant_id)})


async def test_accepting_a_proposal_writes_a_price_list_entry(
    integration_settings: Settings, postgres_available: bool
) -> None:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable")

    engine = create_async_engine(_ADMIN_URL)
    try:
        tenant_id, _cylinder_type_id, proposal_id = await _seed_pending_proposal(engine)

        price = await _accept(integration_settings, tenant_id=tenant_id, proposal_id=proposal_id)
        assert price == Decimal("960.00")

        async with engine.begin() as conn:
            proposal_row = (
                await conn.execute(
                    text(
                        "SELECT status, reviewed_by FROM tenant.price_list_proposal "
                        "WHERE id = :p"
                    ),
                    {"p": str(proposal_id)},
                )
            ).mappings().one()
            price_list_count = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM tenant.price_list "
                        "WHERE tenant_id = :t AND price = 960.00"
                    ),
                    {"t": str(tenant_id)},
                )
            ).scalar_one()

        assert proposal_row["status"] == "accepted"
        assert proposal_row["reviewed_by"] is not None
        assert price_list_count == 1

        await _cleanup(engine, tenant_id=tenant_id)
    finally:
        await engine.dispose()


async def test_rejecting_a_proposal_writes_no_price_list_entry(
    integration_settings: Settings, postgres_available: bool
) -> None:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable")

    engine = create_async_engine(_ADMIN_URL)
    try:
        tenant_id, _cylinder_type_id, proposal_id = await _seed_pending_proposal(engine)

        await _reject(integration_settings, tenant_id=tenant_id, proposal_id=proposal_id)

        async with engine.begin() as conn:
            proposal_row = (
                await conn.execute(
                    text("SELECT status FROM tenant.price_list_proposal WHERE id = :p"),
                    {"p": str(proposal_id)},
                )
            ).mappings().one()
            price_list_count = (
                await conn.execute(
                    text("SELECT count(*) FROM tenant.price_list WHERE tenant_id = :t"),
                    {"t": str(tenant_id)},
                )
            ).scalar_one()

        assert proposal_row["status"] == "rejected"
        assert price_list_count == 0

        await _cleanup(engine, tenant_id=tenant_id)
    finally:
        await engine.dispose()
