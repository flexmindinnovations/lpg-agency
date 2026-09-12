"""`inventory.reorder_policy` against a real Postgres session — the
admin-set threshold + breach-detection query (AI Operational Intelligence,
Horizon 1 Stage 4).

What is real: a seeded tenant/warehouse/cylinder_type, the upsert, and the
breach-detection JOIN against `inventory.inventory_balance` for three cases
a fetch-then-filter-in-Python approach could get wrong — no balance row at
all (zero stock), a row below the threshold, and a row above it.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.application.inventory.ports import ReorderSignal
    from lpg.config.settings import Settings
    from lpg.domain.common.base import DomainEvent

pytestmark = pytest.mark.integration

_ADMIN_URL = "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:5433/lpg_test"


class _NoopUnitOfWork:
    async def __aenter__(self) -> _NoopUnitOfWork:
        return self

    async def __aexit__(self, *_: object) -> None:
        pass

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass

    def collect_events(self) -> Sequence[DomainEvent]:
        return []


async def _seed_tenant(engine: AsyncEngine) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """tenant -> warehouse -> inventory_location -> two cylinder types, one
    with a low `inventory_balance` row and one comfortably stocked. Returns
    `(tenant_id, inventory_location_id, low_stock_ct_id, well_stocked_ct_id)`.
    """
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'Reorder Smoke', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"reorder-smoke-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
        branch_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.branch (id, tenant_id, name) "
                    "VALUES (gen_random_uuid(), :t, 'Reorder Smoke Branch') RETURNING id"
                ),
                {"t": str(tenant_id)},
            )
        ).scalar_one()
        warehouse_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.warehouse (id, tenant_id, branch_id, name, address_line) "
                    "VALUES (gen_random_uuid(), :t, :b, 'Reorder Smoke WH', '1 Depot Rd') "
                    "RETURNING id"
                ),
                {"t": str(tenant_id), "b": str(branch_id)},
            )
        ).scalar_one()
        location_id = (
            await conn.execute(
                text(
                    "INSERT INTO inventory.inventory_location "
                    "(id, tenant_id, location_type, location_ref_id) "
                    "VALUES (gen_random_uuid(), :t, 'warehouse', :w) RETURNING id"
                ),
                {"t": str(tenant_id), "w": str(warehouse_id)},
            )
        ).scalar_one()
        low_stock_ct_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.cylinder_type (id, tenant_id, name, weight_kg) "
                    "VALUES (gen_random_uuid(), :t, 'Low Stock 14.2kg', 14.2) RETURNING id"
                ),
                {"t": str(tenant_id)},
            )
        ).scalar_one()
        well_stocked_ct_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.cylinder_type (id, tenant_id, name, weight_kg) "
                    "VALUES (gen_random_uuid(), :t, 'Well Stocked 19kg', 19.0) RETURNING id"
                ),
                {"t": str(tenant_id)},
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO inventory.inventory_balance "
                "(id, tenant_id, inventory_location_id, cylinder_type_id, status, quantity) "
                "VALUES (gen_random_uuid(), :t, :loc, :ct, 'filled', 5)"
            ),
            {"t": str(tenant_id), "loc": str(location_id), "ct": str(low_stock_ct_id)},
        )
        await conn.execute(
            text(
                "INSERT INTO inventory.inventory_balance "
                "(id, tenant_id, inventory_location_id, cylinder_type_id, status, quantity) "
                "VALUES (gen_random_uuid(), :t, :loc, :ct, 'filled', 100)"
            ),
            {"t": str(tenant_id), "loc": str(location_id), "ct": str(well_stocked_ct_id)},
        )
    return (
        uuid.UUID(str(tenant_id)),
        uuid.UUID(str(location_id)),
        uuid.UUID(str(low_stock_ct_id)),
        uuid.UUID(str(well_stocked_ct_id)),
    )


async def _seed_zero_stock_cylinder_type(engine: AsyncEngine, *, tenant_id: uuid.UUID) -> uuid.UUID:
    """A cylinder type with a policy but NO `inventory_balance` row at all
    — the zero-on-hand case the `LEFT JOIN` + `COALESCE` must still catch."""
    async with engine.begin() as conn:
        ct_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.cylinder_type (id, tenant_id, name, weight_kg) "
                    "VALUES (gen_random_uuid(), :t, 'Zero Stock 5kg', 5.0) RETURNING id"
                ),
                {"t": str(tenant_id)},
            )
        ).scalar_one()
    return uuid.UUID(str(ct_id))


async def _set_policies(
    integration_settings: Settings,
    *,
    tenant_id: uuid.UUID,
    location_id: uuid.UUID,
    thresholds: dict[uuid.UUID, int],
) -> None:
    from lpg.application.common.tenant import RequestTenantContext
    from lpg.application.inventory.reorder import (
        SetReorderPolicyCommand,
        SetReorderPolicyUseCase,
    )
    from lpg.infrastructure.persistence.database import build_database
    from lpg.infrastructure.persistence.repositories.inventory import (
        SqlAlchemyReorderPolicyRepository,
    )
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    database = build_database(integration_settings)
    database.connect()
    try:
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(
                session, RequestTenantContext(tenant_id=tenant_id)
            ) as uow:
                repo = SqlAlchemyReorderPolicyRepository(uow)
                use_case = SetReorderPolicyUseCase(repo, _NoopUnitOfWork())
                for cylinder_type_id, reorder_point in thresholds.items():
                    await use_case.execute(
                        SetReorderPolicyCommand(
                            tenant_id=tenant_id,
                            inventory_location_id=location_id,
                            cylinder_type_id=cylinder_type_id,
                            reorder_point=reorder_point,
                            safety_stock=0,
                        )
                    )
    finally:
        await database.disconnect()


async def _list_breached(
    integration_settings: Settings, *, tenant_id: uuid.UUID
) -> Sequence[ReorderSignal]:
    from lpg.application.common.tenant import RequestTenantContext
    from lpg.application.inventory.reorder import (
        ListReorderSignalsQuery,
        ListReorderSignalsUseCase,
    )
    from lpg.infrastructure.persistence.database import build_database
    from lpg.infrastructure.persistence.repositories.inventory import (
        SqlAlchemyReorderPolicyRepository,
    )
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    database = build_database(integration_settings)
    database.connect()
    try:
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(
                session, RequestTenantContext(tenant_id=tenant_id)
            ) as uow:
                repo = SqlAlchemyReorderPolicyRepository(uow)
                return await ListReorderSignalsUseCase(repo).execute(
                    ListReorderSignalsQuery(tenant_id=tenant_id)
                )
        return []
    finally:
        await database.disconnect()


async def test_breach_detection_covers_zero_stock_and_below_threshold(
    integration_settings: Settings, postgres_available: bool
) -> None:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable")

    engine = create_async_engine(_ADMIN_URL)
    try:
        tenant_id, location_id, low_stock_ct_id, well_stocked_ct_id = await _seed_tenant(engine)
        zero_stock_ct_id = await _seed_zero_stock_cylinder_type(engine, tenant_id=tenant_id)

        await _set_policies(
            integration_settings,
            tenant_id=tenant_id,
            location_id=location_id,
            thresholds={low_stock_ct_id: 10, well_stocked_ct_id: 10, zero_stock_ct_id: 5},
        )

        signals = await _list_breached(integration_settings, tenant_id=tenant_id)
        breached_ct_ids = {s.cylinder_type_id for s in signals}

        assert low_stock_ct_id in breached_ct_ids
        assert zero_stock_ct_id in breached_ct_ids
        assert well_stocked_ct_id not in breached_ct_ids

        zero_signal = next(s for s in signals if s.cylinder_type_id == zero_stock_ct_id)
        assert zero_signal.on_hand == 0
        low_signal = next(s for s in signals if s.cylinder_type_id == low_stock_ct_id)
        assert low_signal.on_hand == 5

        async with engine.begin() as conn:
            for stmt in (
                "DELETE FROM inventory.reorder_policy WHERE tenant_id = :t",
                "DELETE FROM inventory.inventory_balance WHERE tenant_id = :t",
                "DELETE FROM inventory.inventory_location WHERE tenant_id = :t",
                "DELETE FROM tenant.cylinder_type WHERE tenant_id = :t",
                "DELETE FROM tenant.warehouse WHERE tenant_id = :t",
                "DELETE FROM tenant.branch WHERE tenant_id = :t",
                "DELETE FROM tenant.tenant WHERE id = :t",
            ):
                await conn.execute(text(stmt), {"t": str(tenant_id)})
    finally:
        await engine.dispose()
