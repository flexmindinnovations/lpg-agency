"""Integration tests for TDT (Targeted Delivery Time) rating (Phase 20
subsystem 2) — `SqlAlchemyTdtRatingRepository` plus
`GetQuarterlyTdtRatingUseCase`/`GetLiveTdtProjectionUseCase` end to end
against real Postgres.

The reconciliation test (`test_a_hand_calculated_quarter_reconciles_exactly`)
is this feature's own stated verification requirement (`planning/features/
20-regulatory-compliance/PLAN.md` §"Verification": "TDT computed from
order_status_history reconciles against a hand-calculated quarter").

Every band/fine number seeded here is a TEST FIXTURE — not a real MDG
figure, confirm before go-live.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from lpg.application.common.tenant import RequestTenantContext
from lpg.application.compliance.queries.get_tdt_rating import (
    GetQuarterlyTdtRatingQuery,
    GetQuarterlyTdtRatingUseCase,
)
from lpg.domain.tenant.tenant_configuration import TenantConfiguration
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.models.tenant import TenantModel  # noqa: F401
from lpg.infrastructure.persistence.repositories.compliance import (
    SqlAlchemyTdtRatingRepository,
)
from lpg.infrastructure.persistence.repositories.tenant import (
    SqlAlchemyTenantConfigurationRepository,
)
from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration

# TEST FIXTURE bands/fine schedule — not real MDG figures, confirm before
# go-live.
_TEST_BANDS_CONFIG = {
    "mdg_edition": "TEST-FIXTURE",
    "bands": [
        {"stars": 5, "max_days": 1},
        {"stars": 4, "max_days": 2},
        {"stars": 3, "max_days": 4},
        {"stars": 2, "max_days": 7},
        {"stars": 1, "max_days": None},
    ],
}


@pytest.fixture
async def database(
    integration_settings: Settings, postgres_available: bool
) -> AsyncIterator[Database]:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable")
    db = Database(integration_settings)
    db.connect()
    try:
        yield db
    finally:
        await db.disconnect()


async def _seed_tenant_and_branch(admin_engine: AsyncEngine) -> tuple[uuid.UUID, uuid.UUID]:
    async with admin_engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'TDT Test Co', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"tdt-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
        branch_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.branch (id, tenant_id, name) "
                    "VALUES (gen_random_uuid(), :tenant_id, 'Test Branch') RETURNING id"
                ),
                {"tenant_id": str(tenant_id)},
            )
        ).scalar_one()
    return uuid.UUID(str(tenant_id)), uuid.UUID(str(branch_id))


async def _seed_customer(
    admin_engine: AsyncEngine, *, tenant_id: uuid.UUID, branch_id: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID]:
    async with admin_engine.begin() as conn:
        identity_user_id = (
            await conn.execute(
                text(
                    "INSERT INTO identity.identity_user "
                    "(id, tenant_id, branch_id, email, password_hash, role) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :email, 'x', "
                    "'customer') RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id),
                    "email": f"tdt-{uuid.uuid4().hex[:10]}@example.com",
                },
            )
        ).scalar_one()
        customer_id = (
            await conn.execute(
                text(
                    "INSERT INTO customer.customer "
                    "(id, tenant_id, branch_id, identity_user_id, customer_type, full_name, "
                    "phone_number, consumer_number) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :identity_user_id, "
                    "'domestic', 'TDT Test Customer', :phone, :consumer_number) RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id),
                    "identity_user_id": str(identity_user_id),
                    "phone": f"+91{uuid.uuid4().int % 10**9:09d}",
                    "consumer_number": f"CN{uuid.uuid4().hex[:10]}",
                },
            )
        ).scalar_one()
        address_id = (
            await conn.execute(
                text(
                    "INSERT INTO customer.customer_address "
                    "(id, tenant_id, customer_id, line_1) "
                    "VALUES (gen_random_uuid(), :tenant_id, :customer_id, '123 Test St') "
                    "RETURNING id"
                ),
                {"tenant_id": str(tenant_id), "customer_id": str(customer_id)},
            )
        ).scalar_one()
    return uuid.UUID(str(customer_id)), uuid.UUID(str(address_id))


async def _seed_delivered_order(
    admin_engine: AsyncEngine,
    *,
    tenant_id: uuid.UUID,
    branch_id: uuid.UUID,
    customer_id: uuid.UUID,
    address_id: uuid.UUID,
    booked_at: datetime,
    delivered_at: datetime,
) -> uuid.UUID:
    """Seeds one `orders.order` row plus its `booked`/`delivered`
    `order_status_history` rows at explicit, caller-controlled timestamps
    — direct SQL, not the real order lifecycle, specifically so the
    booking-to-delivery gap is a known, hand-computable value rather than
    real wall-clock time the test would otherwise have to wait out."""
    async with admin_engine.begin() as conn:
        order_id = (
            await conn.execute(
                text(
                    "INSERT INTO orders.order "
                    "(id, tenant_id, branch_id, customer_id, address_id, "
                    "delivery_address_line, status, booking_source, requested_date) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :customer_id, "
                    ":address_id, '123 Test St', 'delivered', 'staff', :requested_date) "
                    "RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id),
                    "customer_id": str(customer_id),
                    "address_id": str(address_id),
                    "requested_date": booked_at,
                },
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO orders.order_status_history "
                "(id, order_id, from_status, to_status, changed_by, changed_at) "
                "VALUES (gen_random_uuid(), :order_id, 'draft', 'booked', "
                "gen_random_uuid(), :changed_at)"
            ),
            {"order_id": str(order_id), "changed_at": booked_at},
        )
        await conn.execute(
            text(
                "INSERT INTO orders.order_status_history "
                "(id, order_id, from_status, to_status, changed_by, changed_at) "
                "VALUES (gen_random_uuid(), :order_id, 'out_for_delivery', 'delivered', "
                "gen_random_uuid(), :changed_at)"
            ),
            {"order_id": str(order_id), "changed_at": delivered_at},
        )
    return uuid.UUID(str(order_id))


async def _seed_cancelled_order(
    admin_engine: AsyncEngine,
    *,
    tenant_id: uuid.UUID,
    branch_id: uuid.UUID,
    customer_id: uuid.UUID,
    address_id: uuid.UUID,
    booked_at: datetime,
    cancelled_at: datetime,
) -> uuid.UUID:
    async with admin_engine.begin() as conn:
        order_id = (
            await conn.execute(
                text(
                    "INSERT INTO orders.order "
                    "(id, tenant_id, branch_id, customer_id, address_id, "
                    "delivery_address_line, status, booking_source, requested_date) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :customer_id, "
                    ":address_id, '123 Test St', 'cancelled', 'staff', :requested_date) "
                    "RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id),
                    "customer_id": str(customer_id),
                    "address_id": str(address_id),
                    "requested_date": booked_at,
                },
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO orders.order_status_history "
                "(id, order_id, from_status, to_status, changed_by, changed_at) "
                "VALUES (gen_random_uuid(), :order_id, 'draft', 'booked', "
                "gen_random_uuid(), :changed_at)"
            ),
            {"order_id": str(order_id), "changed_at": booked_at},
        )
        await conn.execute(
            text(
                "INSERT INTO orders.order_status_history "
                "(id, order_id, from_status, to_status, changed_by, changed_at) "
                "VALUES (gen_random_uuid(), :order_id, 'booked', 'cancelled', "
                "gen_random_uuid(), :changed_at)"
            ),
            {"order_id": str(order_id), "changed_at": cancelled_at},
        )
    return uuid.UUID(str(order_id))


async def _seed_bands_config(database: Database, *, tenant_id: uuid.UUID) -> None:
    context = RequestTenantContext(tenant_id=tenant_id)
    async for session in database.open_session(tenant_id=tenant_id):
        async with SqlAlchemyUnitOfWork(session, context) as uow:
            repo = SqlAlchemyTenantConfigurationRepository(uow)
            await repo.add(
                TenantConfiguration(
                    uuid.uuid4(),
                    tenant_id,
                    "tdt_star_rating_bands",
                    _TEST_BANDS_CONFIG,
                    datetime(2020, 1, 1, tzinfo=UTC),
                )
            )
            await uow.commit()


class TestTdtQuarterlyRatingReconciliation:
    async def test_a_hand_calculated_quarter_reconciles_exactly(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id, branch_id = await _seed_tenant_and_branch(admin_engine)
        customer_id, address_id = await _seed_customer(
            admin_engine, tenant_id=tenant_id, branch_id=branch_id
        )
        await _seed_bands_config(database, tenant_id=tenant_id)

        quarter_start = datetime(2026, 1, 1, tzinfo=UTC)
        quarter_end = datetime(2026, 4, 1, tzinfo=UTC)

        # Hand-calculated: 3 orders delivered same-day (0 days -> 5 stars),
        # 2 orders delivered in 3 days (-> 3 stars), 1 order delivered in
        # 10 days (-> 1 star, the unbounded catch-all). Mean =
        # (5*3 + 3*2 + 1*1) / 6 = 22/6 = 3.667 -> rounds to 4.
        booked_at = datetime(2026, 2, 1, tzinfo=UTC)
        day_offsets = [0, 0, 0, 3, 3, 10]
        for day_offset in day_offsets:
            await _seed_delivered_order(
                admin_engine,
                tenant_id=tenant_id,
                branch_id=branch_id,
                customer_id=customer_id,
                address_id=address_id,
                booked_at=booked_at,
                delivered_at=datetime(2026, 2, 1 + day_offset, tzinfo=UTC),
            )

        context = RequestTenantContext(tenant_id=tenant_id)
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                use_case = GetQuarterlyTdtRatingUseCase(
                    SqlAlchemyTdtRatingRepository(uow),
                    SqlAlchemyTenantConfigurationRepository(uow),
                )
                rating = await use_case.execute(
                    GetQuarterlyTdtRatingQuery(
                        tenant_id=tenant_id,
                        quarter_start=quarter_start.date(),
                        quarter_end=quarter_end.date(),
                    )
                )

        assert rating.total_orders == 6
        assert rating.overall_stars == 4
        distribution = {entry.stars: entry.order_count for entry in rating.distribution}
        assert distribution == {5: 3, 3: 2, 1: 1}

    async def test_orders_delivered_outside_the_window_are_excluded(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id, branch_id = await _seed_tenant_and_branch(admin_engine)
        customer_id, address_id = await _seed_customer(
            admin_engine, tenant_id=tenant_id, branch_id=branch_id
        )
        await _seed_bands_config(database, tenant_id=tenant_id)

        # Delivered in Q4 2025, not Q1 2026 — must not appear in Q1's
        # rating even though its booking date is close to the boundary.
        await _seed_delivered_order(
            admin_engine,
            tenant_id=tenant_id,
            branch_id=branch_id,
            customer_id=customer_id,
            address_id=address_id,
            booked_at=datetime(2025, 12, 30, tzinfo=UTC),
            delivered_at=datetime(2025, 12, 31, tzinfo=UTC),
        )

        context = RequestTenantContext(tenant_id=tenant_id)
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                use_case = GetQuarterlyTdtRatingUseCase(
                    SqlAlchemyTdtRatingRepository(uow),
                    SqlAlchemyTenantConfigurationRepository(uow),
                )
                rating = await use_case.execute(
                    GetQuarterlyTdtRatingQuery(
                        tenant_id=tenant_id,
                        quarter_start=date(2026, 1, 1),
                        quarter_end=date(2026, 4, 1),
                    )
                )

        assert rating.total_orders == 0
        assert rating.overall_stars is None

    async def test_an_order_booked_in_a_prior_quarter_still_counts_its_true_gap(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        """The exact bug the two-pass repository query design exists to
        avoid: an order booked near the end of one quarter and delivered
        early in the next must not have its booked_at silently dropped by
        a naive single-pass window filter."""
        tenant_id, branch_id = await _seed_tenant_and_branch(admin_engine)
        customer_id, address_id = await _seed_customer(
            admin_engine, tenant_id=tenant_id, branch_id=branch_id
        )
        await _seed_bands_config(database, tenant_id=tenant_id)

        # Booked in Q4 2025, delivered 10 days later in Q1 2026 -> 1 star
        # (the catch-all band), not silently dropped or miscounted.
        await _seed_delivered_order(
            admin_engine,
            tenant_id=tenant_id,
            branch_id=branch_id,
            customer_id=customer_id,
            address_id=address_id,
            booked_at=datetime(2025, 12, 27, tzinfo=UTC),
            delivered_at=datetime(2026, 1, 6, tzinfo=UTC),
        )

        context = RequestTenantContext(tenant_id=tenant_id)
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                use_case = GetQuarterlyTdtRatingUseCase(
                    SqlAlchemyTdtRatingRepository(uow),
                    SqlAlchemyTenantConfigurationRepository(uow),
                )
                rating = await use_case.execute(
                    GetQuarterlyTdtRatingQuery(
                        tenant_id=tenant_id,
                        quarter_start=date(2026, 1, 1),
                        quarter_end=date(2026, 4, 1),
                    )
                )

        assert rating.total_orders == 1
        assert rating.overall_stars == 1

    async def test_a_cancelled_order_is_excluded_from_the_rating(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id, branch_id = await _seed_tenant_and_branch(admin_engine)
        customer_id, address_id = await _seed_customer(
            admin_engine, tenant_id=tenant_id, branch_id=branch_id
        )
        await _seed_bands_config(database, tenant_id=tenant_id)
        await _seed_cancelled_order(
            admin_engine,
            tenant_id=tenant_id,
            branch_id=branch_id,
            customer_id=customer_id,
            address_id=address_id,
            booked_at=datetime(2026, 2, 1, tzinfo=UTC),
            cancelled_at=datetime(2026, 2, 2, tzinfo=UTC),
        )

        context = RequestTenantContext(tenant_id=tenant_id)
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                use_case = GetQuarterlyTdtRatingUseCase(
                    SqlAlchemyTdtRatingRepository(uow),
                    SqlAlchemyTenantConfigurationRepository(uow),
                )
                rating = await use_case.execute(
                    GetQuarterlyTdtRatingQuery(
                        tenant_id=tenant_id,
                        quarter_start=date(2026, 1, 1),
                        quarter_end=date(2026, 4, 1),
                    )
                )

        assert rating.total_orders == 0
        assert rating.overall_stars is None

    async def test_branch_filter_excludes_other_branches_orders(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id, branch_a = await _seed_tenant_and_branch(admin_engine)
        async with admin_engine.begin() as conn:
            branch_b = (
                await conn.execute(
                    text(
                        "INSERT INTO tenant.branch (id, tenant_id, name) "
                        "VALUES (gen_random_uuid(), :tenant_id, 'Second Branch') RETURNING id"
                    ),
                    {"tenant_id": str(tenant_id)},
                )
            ).scalar_one()
        branch_b = uuid.UUID(str(branch_b))
        customer_id, address_id = await _seed_customer(
            admin_engine, tenant_id=tenant_id, branch_id=branch_a
        )
        await _seed_bands_config(database, tenant_id=tenant_id)

        await _seed_delivered_order(
            admin_engine,
            tenant_id=tenant_id,
            branch_id=branch_a,
            customer_id=customer_id,
            address_id=address_id,
            booked_at=datetime(2026, 2, 1, tzinfo=UTC),
            delivered_at=datetime(2026, 2, 1, tzinfo=UTC),
        )
        await _seed_delivered_order(
            admin_engine,
            tenant_id=tenant_id,
            branch_id=branch_b,
            customer_id=customer_id,
            address_id=address_id,
            booked_at=datetime(2026, 2, 1, tzinfo=UTC),
            delivered_at=datetime(2026, 2, 1, tzinfo=UTC),
        )

        context = RequestTenantContext(tenant_id=tenant_id)
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                use_case = GetQuarterlyTdtRatingUseCase(
                    SqlAlchemyTdtRatingRepository(uow),
                    SqlAlchemyTenantConfigurationRepository(uow),
                )
                rating = await use_case.execute(
                    GetQuarterlyTdtRatingQuery(
                        tenant_id=tenant_id,
                        quarter_start=date(2026, 1, 1),
                        quarter_end=date(2026, 4, 1),
                        branch_id=branch_a,
                    )
                )

        assert rating.total_orders == 1

    async def test_no_bands_configured_yields_no_rating(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id, branch_id = await _seed_tenant_and_branch(admin_engine)
        customer_id, address_id = await _seed_customer(
            admin_engine, tenant_id=tenant_id, branch_id=branch_id
        )
        # Deliberately no _seed_bands_config call.
        await _seed_delivered_order(
            admin_engine,
            tenant_id=tenant_id,
            branch_id=branch_id,
            customer_id=customer_id,
            address_id=address_id,
            booked_at=datetime(2026, 2, 1, tzinfo=UTC),
            delivered_at=datetime(2026, 2, 1, tzinfo=UTC),
        )

        context = RequestTenantContext(tenant_id=tenant_id)
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                use_case = GetQuarterlyTdtRatingUseCase(
                    SqlAlchemyTdtRatingRepository(uow),
                    SqlAlchemyTenantConfigurationRepository(uow),
                )
                rating = await use_case.execute(
                    GetQuarterlyTdtRatingQuery(
                        tenant_id=tenant_id,
                        quarter_start=date(2026, 1, 1),
                        quarter_end=date(2026, 4, 1),
                    )
                )

        assert rating.overall_stars is None


class TestTdtRatingCrossTenantIsolation:
    async def test_a_tenants_order_history_never_leaks_to_another_tenant(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        """`order_status_history` has no `tenant_id` column and no RLS
        policy of its own — this test exercises the *only* mechanism that
        isolates it, the join to the RLS-protected `orders.order` table,
        rather than trusting the general RLS suite (which never touches
        this specific no-RLS-of-its-own table) to have covered it."""
        tenant_a, branch_a = await _seed_tenant_and_branch(admin_engine)
        customer_a, address_a = await _seed_customer(
            admin_engine, tenant_id=tenant_a, branch_id=branch_a
        )
        await _seed_bands_config(database, tenant_id=tenant_a)
        await _seed_delivered_order(
            admin_engine,
            tenant_id=tenant_a,
            branch_id=branch_a,
            customer_id=customer_a,
            address_id=address_a,
            booked_at=datetime(2026, 2, 1, tzinfo=UTC),
            delivered_at=datetime(2026, 2, 1, tzinfo=UTC),
        )

        tenant_b, _branch_b = await _seed_tenant_and_branch(admin_engine)
        await _seed_bands_config(database, tenant_id=tenant_b)

        context_b = RequestTenantContext(tenant_id=tenant_b)
        async for session in database.open_session(tenant_id=tenant_b):
            async with SqlAlchemyUnitOfWork(session, context_b) as uow:
                use_case = GetQuarterlyTdtRatingUseCase(
                    SqlAlchemyTdtRatingRepository(uow),
                    SqlAlchemyTenantConfigurationRepository(uow),
                )
                rating = await use_case.execute(
                    GetQuarterlyTdtRatingQuery(
                        tenant_id=tenant_b,
                        quarter_start=date(2026, 1, 1),
                        quarter_end=date(2026, 4, 1),
                    )
                )

        assert rating.total_orders == 0
        assert rating.overall_stars is None
