from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import selectinload

from lpg.domain.customer.customer import Customer, CustomerAddress, KycDocument
from lpg.infrastructure.persistence.models.customer import (
    CustomerAddressModel,
    CustomerModel,
    CustomerNumberSequenceModel,
    KycDocumentModel,
)

if TYPE_CHECKING:
    from lpg.application.customer.ports import FieldEncryptor
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyCustomerRepository:
    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork, field_encryptor: FieldEncryptor) -> None:
        self._uow = unit_of_work
        self._field_encryptor = field_encryptor

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    def _to_domain(self, row: CustomerModel) -> Customer:
        addresses = [
            CustomerAddress(
                address_id=addr.id,
                address_line=addr.address_line,
                latitude=float(addr.latitude) if addr.latitude is not None else None,
                longitude=float(addr.longitude) if addr.longitude is not None else None,
                is_primary=addr.is_primary,
            )
            for addr in row.addresses
            if not addr.is_deleted
        ]

        kyc_docs = [
            KycDocument(
                document_id=doc.id,
                doc_type=doc.doc_type,
                doc_reference=self._field_encryptor.decrypt(doc.doc_reference),
                verification_status=doc.verification_status,
                verified_by=doc.verified_by,
                verified_at=doc.verified_at,
            )
            for doc in row.kyc_documents
            if not doc.is_deleted
        ]

        customer = Customer(
            customer_id=row.id,
            tenant_id=row.tenant_id,
            branch_id=row.branch_id,
            consumer_number=row.consumer_number,
            full_name=row.full_name,
            phone_number=row.phone_number,
            customer_type=row.customer_type,
            kyc_status=row.kyc_status,
            status=row.status,
            lpg_subsidy_id=row.lpg_subsidy_id,
            addresses=addresses,
            kyc_documents=kyc_docs,
            identity_user_id=row.identity_user_id,
            version=row.version,
        )
        self._uow.register_aggregate(customer)
        return customer

    async def get_by_id(self, customer_id: uuid.UUID) -> Customer | None:
        stmt = (
            select(CustomerModel)
            .options(
                selectinload(CustomerModel.addresses),
                selectinload(CustomerModel.kyc_documents),
            )
            .where(CustomerModel.id == customer_id, CustomerModel.is_deleted.is_(False))
        )
        result = await self._uow.session.execute(stmt)
        row = result.scalars().first()
        if row is None:
            return None
        return self._to_domain(row)

    async def get_by_phone(self, phone_number: str) -> Customer | None:
        stmt = (
            select(CustomerModel)
            .options(
                selectinload(CustomerModel.addresses),
                selectinload(CustomerModel.kyc_documents),
            )
            .where(CustomerModel.phone_number == phone_number, CustomerModel.is_deleted.is_(False))
        )
        result = await self._uow.session.execute(stmt)
        row = result.scalars().first()
        if row is None:
            return None
        return self._to_domain(row)

    async def get_by_consumer_number(self, consumer_number: str) -> Customer | None:
        stmt = (
            select(CustomerModel)
            .options(
                selectinload(CustomerModel.addresses),
                selectinload(CustomerModel.kyc_documents),
            )
            .where(
                CustomerModel.consumer_number == consumer_number,
                CustomerModel.is_deleted.is_(False),
            )
        )
        result = await self._uow.session.execute(stmt)
        row = result.scalars().first()
        if row is None:
            return None
        return self._to_domain(row)

    async def get_by_lpg_subsidy_id(self, lpg_subsidy_id: str) -> Customer | None:
        stmt = (
            select(CustomerModel)
            .options(
                selectinload(CustomerModel.addresses),
                selectinload(CustomerModel.kyc_documents),
            )
            .where(
                CustomerModel.lpg_subsidy_id == lpg_subsidy_id,
                CustomerModel.is_deleted.is_(False),
            )
        )
        result = await self._uow.session.execute(stmt)
        row = result.scalars().first()
        if row is None:
            return None
        return self._to_domain(row)

    async def get_by_identity_user_id(self, identity_user_id: uuid.UUID) -> Customer | None:
        stmt = (
            select(CustomerModel)
            .options(
                selectinload(CustomerModel.addresses),
                selectinload(CustomerModel.kyc_documents),
            )
            .where(
                CustomerModel.identity_user_id == identity_user_id,
                CustomerModel.is_deleted.is_(False),
            )
        )
        result = await self._uow.session.execute(stmt)
        row = result.scalars().first()
        if row is None:
            return None
        return self._to_domain(row)

    async def save(self, customer: Customer) -> None:
        # Check if row exists in database
        stmt = (
            select(CustomerModel)
            .options(
                selectinload(CustomerModel.addresses),
                selectinload(CustomerModel.kyc_documents),
            )
            .where(CustomerModel.id == customer.id)
        )
        row = (await self._uow.session.execute(stmt)).scalars().first()

        if row is None:
            # Create new row
            row = CustomerModel(
                id=customer.id,
                tenant_id=customer.tenant_id,
                branch_id=customer.branch_id,
                consumer_number=customer.consumer_number,
                full_name=customer.full_name,
                phone_number=customer.phone_number,
                customer_type=customer.customer_type,
                kyc_status=customer.kyc_status,
                status=customer.status,
                lpg_subsidy_id=customer.lpg_subsidy_id,
                identity_user_id=customer.identity_user_id,
            )
            self._uow.session.add(row)
        else:
            # Update existing row
            row.branch_id = customer.branch_id
            row.full_name = customer.full_name
            row.phone_number = customer.phone_number
            row.customer_type = customer.customer_type
            row.kyc_status = customer.kyc_status
            row.status = customer.status
            row.lpg_subsidy_id = customer.lpg_subsidy_id
            row.identity_user_id = customer.identity_user_id
            row.version = customer.version

        # Sync Addresses
        existing_addrs = {addr.id: addr for addr in row.addresses}
        domain_addrs = {addr.id: addr for addr in customer.addresses}

        for addr_id, domain_addr in domain_addrs.items():
            if addr_id in existing_addrs:
                existing_addr = existing_addrs[addr_id]
                existing_addr.address_line = domain_addr.address_line
                existing_addr.latitude = (
                    Decimal(str(domain_addr.latitude)) if domain_addr.latitude is not None else None
                )
                existing_addr.longitude = (
                    Decimal(str(domain_addr.longitude))
                    if domain_addr.longitude is not None
                    else None
                )
                existing_addr.is_primary = domain_addr.is_primary
                existing_addr.is_deleted = False
            else:
                new_addr = CustomerAddressModel(
                    id=domain_addr.id,
                    tenant_id=customer.tenant_id,
                    customer_id=customer.id,
                    address_line=domain_addr.address_line,
                    latitude=(
                        Decimal(str(domain_addr.latitude))
                        if domain_addr.latitude is not None
                        else None
                    ),
                    longitude=(
                        Decimal(str(domain_addr.longitude))
                        if domain_addr.longitude is not None
                        else None
                    ),
                    is_primary=domain_addr.is_primary,
                )
                self._uow.session.add(new_addr)

        # Soft delete addresses no longer in the domain model
        for addr_id, existing_addr in existing_addrs.items():
            if addr_id not in domain_addrs:
                existing_addr.is_deleted = True

        # Sync KYC Documents
        existing_docs = {doc.id: doc for doc in row.kyc_documents}
        domain_docs = {doc.id: doc for doc in customer.kyc_documents}

        for doc_id, domain_doc in domain_docs.items():
            if doc_id in existing_docs:
                existing_doc = existing_docs[doc_id]
                existing_doc.doc_type = domain_doc.doc_type
                existing_doc.doc_reference = self._field_encryptor.encrypt(domain_doc.doc_reference)
                existing_doc.verification_status = domain_doc.verification_status
                existing_doc.verified_by = domain_doc.verified_by
                existing_doc.verified_at = domain_doc.verified_at
                existing_doc.is_deleted = False
            else:
                new_doc = KycDocumentModel(
                    id=domain_doc.id,
                    tenant_id=customer.tenant_id,
                    customer_id=customer.id,
                    doc_type=domain_doc.doc_type,
                    doc_reference=self._field_encryptor.encrypt(domain_doc.doc_reference),
                    verification_status=domain_doc.verification_status,
                    verified_by=domain_doc.verified_by,
                    verified_at=domain_doc.verified_at,
                )
                self._uow.session.add(new_doc)

        for doc_id, existing_doc in existing_docs.items():
            if doc_id not in domain_docs:
                existing_doc.is_deleted = True

        self._uow.register_aggregate(customer)

    async def list_customers(
        self,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
    ) -> list[Customer]:
        stmt = (
            select(CustomerModel)
            .options(
                selectinload(CustomerModel.addresses),
                selectinload(CustomerModel.kyc_documents),
            )
            .where(CustomerModel.is_deleted.is_(False))
        )

        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    CustomerModel.full_name.ilike(search_pattern),
                    CustomerModel.phone_number.ilike(search_pattern),
                    CustomerModel.consumer_number.ilike(search_pattern),
                )
            )

        stmt = stmt.order_by(CustomerModel.full_name).offset(skip).limit(limit)
        result = await self._uow.session.execute(stmt)
        return [self._to_domain(row) for row in result.scalars()]

    async def count_customers(self, search: str | None = None) -> int:
        stmt = select(func.count(CustomerModel.id)).where(CustomerModel.is_deleted.is_(False))
        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    CustomerModel.full_name.ilike(search_pattern),
                    CustomerModel.phone_number.ilike(search_pattern),
                    CustomerModel.consumer_number.ilike(search_pattern),
                )
            )
        result = await self._uow.session.execute(stmt)
        return result.scalar() or 0


class SqlAlchemyConsumerNumberSequence:
    """`INSERT ... ON CONFLICT ... DO UPDATE ... RETURNING` against
    `customer.customer_number_sequence` — Postgres serializes concurrent
    upserts to the same `tenant_id` row via its own row-level lock, so two
    staff registering customers at the same moment never get the same
    suggested number, without any application-level locking.
    """

    _PREFIX = "CN-"
    _PAD_WIDTH = 6

    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork, tenant_id: uuid.UUID) -> None:
        self._uow = unit_of_work
        self._tenant_id = tenant_id

    async def next(self) -> str:
        stmt = (
            pg_insert(CustomerNumberSequenceModel)
            .values(tenant_id=self._tenant_id, next_value=2)
            .on_conflict_do_update(
                index_elements=[CustomerNumberSequenceModel.tenant_id],
                set_={
                    "next_value": CustomerNumberSequenceModel.next_value + 1,
                },
            )
            .returning(CustomerNumberSequenceModel.next_value)
        )
        result = await self._uow.session.execute(stmt)
        # The row now holds the *next* value after this one — this call's
        # own number is one less than what was just written.
        new_next_value = result.scalar_one()
        this_value = new_next_value - 1
        return f"{self._PREFIX}{this_value:0{self._PAD_WIDTH}d}"
