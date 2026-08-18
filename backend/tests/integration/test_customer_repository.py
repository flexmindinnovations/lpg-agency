from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from lpg.application.common.tenant import RequestTenantContext
from lpg.domain.customer.customer import Customer
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.models.identity import IdentityUserModel  # noqa: F401
from lpg.infrastructure.persistence.models.tenant import BranchModel, TenantModel  # noqa: F401
from lpg.infrastructure.persistence.repositories.customer import (
    SqlAlchemyConsumerNumberSequence,
    SqlAlchemyCustomerRepository,
)
from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from lpg.infrastructure.security.field_encryption import FernetFieldEncryptor

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
                    "VALUES (gen_random_uuid(), 'Customer Test Co', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"customer-test-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
    return uuid.UUID(str(tenant_id))


async def _seed_branch(admin_engine: AsyncEngine, *, tenant_id: uuid.UUID, name: str) -> uuid.UUID:
    async with admin_engine.begin() as conn:
        branch_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.branch (id, tenant_id, name) "
                    "VALUES (gen_random_uuid(), :tenant_id, :name) RETURNING id"
                ),
                {"tenant_id": str(tenant_id), "name": name},
            )
        ).scalar_one()
    return uuid.UUID(str(branch_id))


class TestCustomerRepository:
    async def test_save_then_get_round_trips(
        self, database: Database, admin_engine: AsyncEngine, integration_settings: Settings
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        branch_id = await _seed_branch(admin_engine, tenant_id=tenant_id, name="Test Branch")
        context = RequestTenantContext(tenant_id=tenant_id)
        field_encryptor = FernetFieldEncryptor(integration_settings)

        customer_id = uuid.uuid4()

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repo = SqlAlchemyCustomerRepository(uow, field_encryptor)
                customer = Customer(
                    customer_id=customer_id,
                    tenant_id=tenant_id,
                    branch_id=branch_id,
                    consumer_number="CN-999",
                    full_name="Alice Smith",
                    phone_number="+1234567890",
                )
                customer.add_address("123 Main St")
                customer.submit_kyc("aadhaar", "REF-A123")
                await repo.save(customer)

        async for verify_session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(verify_session, context) as uow:
                repo = SqlAlchemyCustomerRepository(uow, field_encryptor)
                reloaded = await repo.get_by_id(customer_id)
                assert reloaded is not None
                assert reloaded.full_name == "Alice Smith"
                assert reloaded.phone_number == "+1234567890"
                assert len(reloaded.addresses) == 1
                assert reloaded.addresses[0].line_1 == "123 Main St"
                assert len(reloaded.kyc_documents) == 1
                assert reloaded.kyc_documents[0].doc_type == "aadhaar"
                # Decrypted back to the original plaintext reference.
                assert reloaded.kyc_documents[0].document_number == "REF-A123"

    async def test_kyc_doc_reference_is_encrypted_at_rest(
        self,
        database: Database,
        admin_engine: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        branch_id = await _seed_branch(admin_engine, tenant_id=tenant_id, name="Test Branch")
        context = RequestTenantContext(tenant_id=tenant_id)
        field_encryptor = FernetFieldEncryptor(integration_settings)

        customer_id = uuid.uuid4()
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repo = SqlAlchemyCustomerRepository(uow, field_encryptor)
                customer = Customer(
                    customer_id=customer_id,
                    tenant_id=tenant_id,
                    branch_id=branch_id,
                    consumer_number="CN-998",
                    full_name="Carla Diaz",
                    phone_number="+1234567891",
                )
                customer.submit_kyc("aadhaar", "PLAINTEXT-AADHAAR-REF")
                await repo.save(customer)

        async with admin_engine.begin() as conn:
            raw_reference = (
                await conn.execute(
                    text(
                        "SELECT document_number FROM customer.kyc_document "
                        "WHERE customer_id = :customer_id"
                    ),
                    {"customer_id": str(customer_id)},
                )
            ).scalar_one()

            # Verify the audit log does not store the plaintext either
            audit_rows = (
                (
                    await conn.execute(
                        text(
                            "SELECT after_state FROM audit.audit_log "
                            "WHERE entity_name = 'kyc_document' AND entity_id = "
                            "(SELECT id::text FROM customer.kyc_document "
                            "WHERE customer_id = :customer_id)"
                        ),
                        {"customer_id": str(customer_id)},
                    )
                )
                .scalars()
                .all()
            )

        assert raw_reference != "PLAINTEXT-AADHAAR-REF"
        assert field_encryptor.decrypt(raw_reference) == "PLAINTEXT-AADHAAR-REF"

        for state in audit_rows:
            if state and "document_number" in state:
                assert state["document_number"] != "PLAINTEXT-AADHAAR-REF"
                assert field_encryptor.decrypt(state["document_number"]) == "PLAINTEXT-AADHAAR-REF"

    async def test_get_by_lpg_subsidy_id_round_trips(
        self, database: Database, admin_engine: AsyncEngine, integration_settings: Settings
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        branch_id = await _seed_branch(admin_engine, tenant_id=tenant_id, name="Test Branch")
        context = RequestTenantContext(tenant_id=tenant_id)
        field_encryptor = FernetFieldEncryptor(integration_settings)

        customer_id = uuid.uuid4()
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repo = SqlAlchemyCustomerRepository(uow, field_encryptor)
                customer = Customer(
                    customer_id=customer_id,
                    tenant_id=tenant_id,
                    branch_id=branch_id,
                    consumer_number="CN-997",
                    full_name="Deepa Rao",
                    phone_number="+1234567892",
                    lpg_subsidy_id="98765432109876543",
                )
                await repo.save(customer)

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                repo = SqlAlchemyCustomerRepository(uow, field_encryptor)
                reloaded = await repo.get_by_lpg_subsidy_id("98765432109876543")
                assert reloaded is not None
                assert reloaded.id == customer_id
                assert reloaded.lpg_subsidy_id == "98765432109876543"

    async def test_cannot_see_another_tenants_customer(
        self, database: Database, admin_engine: AsyncEngine, integration_settings: Settings
    ) -> None:
        tenant_1 = await _seed_tenant(admin_engine)
        branch_1 = await _seed_branch(admin_engine, tenant_id=tenant_1, name="Branch 1")
        tenant_2 = await _seed_tenant(admin_engine)
        field_encryptor = FernetFieldEncryptor(integration_settings)

        # Save a customer in Tenant 1
        customer_id = uuid.uuid4()
        context_1 = RequestTenantContext(tenant_id=tenant_1)
        async for session in database.open_session(tenant_id=tenant_1):
            async with SqlAlchemyUnitOfWork(session, context_1) as uow:
                repo = SqlAlchemyCustomerRepository(uow, field_encryptor)
                customer = Customer(
                    customer_id=customer_id,
                    tenant_id=tenant_1,
                    branch_id=branch_1,
                    consumer_number="CN-111",
                    full_name="Bob Jones",
                    phone_number="+9876543210",
                )
                await repo.save(customer)

        # Try to retrieve it using Tenant 2's session context
        context_2 = RequestTenantContext(tenant_id=tenant_2)
        async for session in database.open_session(tenant_id=tenant_2):
            async with SqlAlchemyUnitOfWork(session, context_2) as uow:
                repo = SqlAlchemyCustomerRepository(uow, field_encryptor)
                reloaded = await repo.get_by_id(customer_id)
                assert reloaded is None  # RLS filters it out


class TestConsumerNumberSequence:
    async def test_next_increments_sequentially(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        context = RequestTenantContext(tenant_id=tenant_id)

        values = []
        for _ in range(3):
            async for session in database.open_session(tenant_id=tenant_id):
                async with SqlAlchemyUnitOfWork(session, context) as uow:
                    sequence = SqlAlchemyConsumerNumberSequence(uow, tenant_id)
                    values.append(await sequence.next())
                    await uow.commit()

        assert values == ["CN-000001", "CN-000002", "CN-000003"]

    async def test_next_is_independent_per_tenant(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_1 = await _seed_tenant(admin_engine)
        tenant_2 = await _seed_tenant(admin_engine)

        context_1 = RequestTenantContext(tenant_id=tenant_1)
        async for session in database.open_session(tenant_id=tenant_1):
            async with SqlAlchemyUnitOfWork(session, context_1) as uow:
                sequence_1 = SqlAlchemyConsumerNumberSequence(uow, tenant_1)
                first = await sequence_1.next()
                await uow.commit()

        context_2 = RequestTenantContext(tenant_id=tenant_2)
        async for session in database.open_session(tenant_id=tenant_2):
            async with SqlAlchemyUnitOfWork(session, context_2) as uow:
                sequence_2 = SqlAlchemyConsumerNumberSequence(uow, tenant_2)
                second = await sequence_2.next()
                await uow.commit()

        # Each tenant's counter starts fresh at 1, independently of the other.
        assert first == "CN-000001"
        assert second == "CN-000001"
