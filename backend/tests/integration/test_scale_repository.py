"""Integration tests for SqlAlchemyScaleRepository — round-trip, the update
path (replace certificate / set status), RLS isolation, and the expiry
filter (Weighment Part 1)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from lpg.application.common.tenant import RequestTenantContext
from lpg.domain.compliance.scale import Scale
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.models.tenant import TenantModel  # noqa: F401
from lpg.infrastructure.persistence.repositories.compliance import (
    SqlAlchemyScaleRepository,
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
        pytest.skip("PostgreSQL is not reachable")
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
                    "VALUES (gen_random_uuid(), 'Scale Test Co', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"scale-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
    return uuid.UUID(str(tenant_id))


async def _seed_warehouse(admin_engine: AsyncEngine, tenant_id: uuid.UUID) -> uuid.UUID:
    async with admin_engine.begin() as conn:
        branch_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.branch (id, tenant_id, name) "
                    "VALUES (gen_random_uuid(), :tenant_id, 'Test Branch') RETURNING id"
                ),
                {"tenant_id": str(tenant_id)},
            )
        ).scalar_one()
        warehouse_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.warehouse (id, tenant_id, branch_id, name, address_line) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, 'Test Godown', "
                    "'1 Depot Road') RETURNING id"
                ),
                {"tenant_id": str(tenant_id), "branch_id": str(branch_id)},
            )
        ).scalar_one()
    return uuid.UUID(str(warehouse_id))


def _scale(tenant_id: uuid.UUID, warehouse_id: uuid.UUID, **kw: object) -> Scale:
    defaults: dict[str, object] = {
        "scale_id": uuid.uuid4(),
        "tenant_id": tenant_id,
        "warehouse_id": warehouse_id,
        "asset_tag": f"SCALE-{uuid.uuid4().hex[:6]}",
        "least_count_grams": 10,
        "certificate_ref": "tenant/x/compliance-staging/scale_cert.pdf",
        "certificate_expiry_date": datetime.now(UTC).date() + timedelta(days=365),
    }
    defaults.update(kw)
    return Scale(**defaults)  # type: ignore[arg-type]


class TestScaleRepository:
    async def test_save_and_get_by_id(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        warehouse_id = await _seed_warehouse(admin_engine, tenant_id)
        context = RequestTenantContext(tenant_id=tenant_id)
        scale = _scale(tenant_id, warehouse_id, asset_tag="SCALE-A1")

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                await SqlAlchemyScaleRepository(uow).save(scale)

        async for verify in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(verify, context) as uow:
                repo = SqlAlchemyScaleRepository(uow)
                reloaded = await repo.get_by_id(scale.id)
                assert reloaded is not None
                assert reloaded.asset_tag == "SCALE-A1"
                assert reloaded.status == "active"

                by_tag = await repo.get_by_warehouse_and_asset_tag(warehouse_id, "SCALE-A1")
                assert by_tag is not None and by_tag.id == scale.id

                for_warehouse = await repo.list_for_warehouse(warehouse_id)
                assert [s.id for s in for_warehouse] == [scale.id]

    async def test_replace_certificate_then_set_status_persist(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        warehouse_id = await _seed_warehouse(admin_engine, tenant_id)
        context = RequestTenantContext(tenant_id=tenant_id)
        scale = _scale(tenant_id, warehouse_id)

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                await SqlAlchemyScaleRepository(uow).save(scale)

        async for s2 in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(s2, context) as uow:
                repo = SqlAlchemyScaleRepository(uow)
                loaded = await repo.get_by_id(scale.id)
                assert loaded is not None
                loaded.replace_certificate(
                    certificate_ref="tenant/x/compliance-staging/new_cert.pdf",
                    certificate_expiry_date=datetime.now(UTC).date() + timedelta(days=1000),
                )
                loaded.set_status("inactive")
                await repo.save(loaded)

        async for s3 in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(s3, context) as uow:
                final = await SqlAlchemyScaleRepository(uow).get_by_id(scale.id)
                assert final is not None
                assert final.certificate_ref == "tenant/x/compliance-staging/new_cert.pdf"
                assert final.status == "inactive"

    async def test_rls_hides_another_tenants_scales(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_a = await _seed_tenant(admin_engine)
        warehouse_a = await _seed_warehouse(admin_engine, tenant_a)
        tenant_b = await _seed_tenant(admin_engine)
        scale = _scale(tenant_a, warehouse_a)

        async for session in database.open_session(tenant_id=tenant_a):
            async with SqlAlchemyUnitOfWork(
                session, RequestTenantContext(tenant_id=tenant_a)
            ) as uow:
                await SqlAlchemyScaleRepository(uow).save(scale)

        async for other in database.open_session(tenant_id=tenant_b):
            async with SqlAlchemyUnitOfWork(other, RequestTenantContext(tenant_id=tenant_b)) as uow:
                assert await SqlAlchemyScaleRepository(uow).get_by_id(scale.id) is None

    async def test_list_for_tenant_expiry_filter(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        warehouse_id = await _seed_warehouse(admin_engine, tenant_id)
        context = RequestTenantContext(tenant_id=tenant_id)
        soon = _scale(
            tenant_id,
            warehouse_id,
            asset_tag="SCALE-SOON",
            certificate_expiry_date=datetime.now(UTC).date() + timedelta(days=10),
        )
        far = _scale(
            tenant_id,
            warehouse_id,
            asset_tag="SCALE-FAR",
            certificate_expiry_date=datetime.now(UTC).date() + timedelta(days=400),
        )
        expired = _scale(
            tenant_id,
            warehouse_id,
            asset_tag="SCALE-EXPIRED",
            certificate_expiry_date=datetime.now(UTC).date() - timedelta(days=5),
        )

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repo = SqlAlchemyScaleRepository(uow)
                await repo.save(soon)
                await repo.save(far)
                await repo.save(expired)

        async for s2 in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(s2, context) as uow:
                repo = SqlAlchemyScaleRepository(uow)
                expiring = await repo.list_for_tenant(expiry="expiring")
                assert [s.id for s in expiring] == [soon.id]

                expired_list = await repo.list_for_tenant(expiry="expired")
                assert [s.id for s in expired_list] == [expired.id]

                total = await repo.count_for_tenant()
                assert total == 3
