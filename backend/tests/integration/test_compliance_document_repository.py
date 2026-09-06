"""Integration tests for SqlAlchemyComplianceDocumentRepository — round-trip,
the update path (replace / verify), RLS isolation, and the cron work list."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from lpg.application.common.tenant import RequestTenantContext
from lpg.domain.delivery.compliance_document import ComplianceDocument
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.models.tenant import TenantModel  # noqa: F401
from lpg.infrastructure.persistence.repositories.compliance_document import (
    SqlAlchemyComplianceDocumentRepository,
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
                    "VALUES (gen_random_uuid(), 'Compliance Test Co', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"compliance-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
    return uuid.UUID(str(tenant_id))


async def _seed_user(admin_engine: AsyncEngine, tenant_id: uuid.UUID) -> uuid.UUID:
    async with admin_engine.begin() as conn:
        user_id = (
            await conn.execute(
                text(
                    "INSERT INTO identity.identity_user "
                    "(id, tenant_id, email, password_hash, role) "
                    "VALUES (gen_random_uuid(), :tenant_id, :email, 'x', 'manager') RETURNING id"
                ),
                {"tenant_id": str(tenant_id), "email": f"rev-{uuid.uuid4().hex[:8]}@example.com"},
            )
        ).scalar_one()
    return uuid.UUID(str(user_id))


def _doc(tenant_id: uuid.UUID, owner_id: uuid.UUID, **kw: object) -> ComplianceDocument:
    defaults: dict[str, object] = {
        "document_id": uuid.uuid4(),
        "tenant_id": tenant_id,
        "owner_type": "driver",
        "owner_id": owner_id,
        "doc_type": "driving_licence",
        "document_number": "MH1220110012345",
        "file_ref": "tenant/x/compliance-staging/dl.png",
        "expiry_date": datetime.now(UTC).date() + timedelta(days=365),
    }
    defaults.update(kw)
    return ComplianceDocument(**defaults)  # type: ignore[arg-type]


class TestComplianceDocumentRepository:
    async def test_save_get_and_list_by_owner(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        context = RequestTenantContext(tenant_id=tenant_id)
        owner_id = uuid.uuid4()
        doc = _doc(tenant_id, owner_id)

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repo = SqlAlchemyComplianceDocumentRepository(uow)
                await repo.save(doc)

        async for verify in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(verify, context) as uow:
                repo = SqlAlchemyComplianceDocumentRepository(uow)
                reloaded = await repo.get_by_id(doc.id)
                assert reloaded is not None
                assert reloaded.document_number == "MH1220110012345"
                assert reloaded.verification_status == "pending"

                by_owner = await repo.list_by_owner("driver", owner_id)
                assert [d.id for d in by_owner] == [doc.id]

                same_type = await repo.get_for_owner_and_type("driver", owner_id, "driving_licence")
                assert same_type is not None and same_type.id == doc.id

    async def test_replace_then_verify_persist_through_the_update_path(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        context = RequestTenantContext(tenant_id=tenant_id)
        doc = _doc(tenant_id, uuid.uuid4())
        reviewer = await _seed_user(admin_engine, tenant_id)

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                await SqlAlchemyComplianceDocumentRepository(uow).save(doc)

        async for s2 in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(s2, context) as uow:
                repo = SqlAlchemyComplianceDocumentRepository(uow)
                loaded = await repo.get_by_id(doc.id)
                assert loaded is not None
                loaded.replace(
                    document_number="MH1220110099999",
                    file_ref="tenant/x/compliance-staging/dl2.png",
                    issue_date=None,
                    expiry_date=datetime.now(UTC).date() + timedelta(days=1000),
                )
                loaded.verify(status="verified", verified_by=reviewer)
                await repo.save(loaded)

        async for s3 in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(s3, context) as uow:
                final = await SqlAlchemyComplianceDocumentRepository(uow).get_by_id(doc.id)
                assert final is not None
                assert final.document_number == "MH1220110099999"
                assert final.verification_status == "verified"
                assert final.verified_by == reviewer

    async def test_rls_hides_another_tenants_documents(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_a = await _seed_tenant(admin_engine)
        tenant_b = await _seed_tenant(admin_engine)
        doc = _doc(tenant_a, uuid.uuid4())

        async for session in database.open_session(tenant_id=tenant_a):
            async with SqlAlchemyUnitOfWork(
                session, RequestTenantContext(tenant_id=tenant_a)
            ) as uow:
                await SqlAlchemyComplianceDocumentRepository(uow).save(doc)

        async for other in database.open_session(tenant_id=tenant_b):
            async with SqlAlchemyUnitOfWork(other, RequestTenantContext(tenant_id=tenant_b)) as uow:
                assert await SqlAlchemyComplianceDocumentRepository(uow).get_by_id(doc.id) is None

    async def test_list_expiring_returns_only_soon_and_unnotified(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        context = RequestTenantContext(tenant_id=tenant_id)
        soon = _doc(
            tenant_id,
            uuid.uuid4(),
            expiry_date=datetime.now(UTC).date() + timedelta(days=10),
        )
        far = _doc(
            tenant_id,
            uuid.uuid4(),
            doc_type="dl_hazmat_endorsement",
            expiry_date=datetime.now(UTC).date() + timedelta(days=400),
        )

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repo = SqlAlchemyComplianceDocumentRepository(uow)
                await repo.save(soon)
                await repo.save(far)

        async for s2 in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(s2, context) as uow:
                repo = SqlAlchemyComplianceDocumentRepository(uow)
                expiring = await repo.list_expiring(within_days=30)
                assert [d.id for d in expiring] == [soon.id]

                await repo.mark_expiry_notified(soon.id)

        async for s3 in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(s3, context) as uow:
                repo = SqlAlchemyComplianceDocumentRepository(uow)
                assert await repo.list_expiring(within_days=30) == []
