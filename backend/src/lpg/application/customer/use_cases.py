from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command, Query
from lpg.application.common.errors import (
    DuplicateConsumerNumberError,
    DuplicateLpgSubsidyIdError,
    DuplicatePhoneError,
    NotFoundError,
)
from lpg.domain.customer.customer import Customer

if TYPE_CHECKING:
    import datetime
    import uuid

    from lpg.application.common.ports import UnitOfWork
    from lpg.application.customer.ports import ConsumerNumberSequence, CustomerRepository


@dataclass(frozen=True, slots=True)
class RegisterCustomerCommand(Command):
    tenant_id: uuid.UUID
    branch_id: uuid.UUID
    full_name: str
    phone_number: str
    consumer_number: str | None = None
    contact_person: str | None = None
    alternate_mobile: str | None = None
    email: str | None = None
    date_of_birth: datetime.date | None = None
    customer_type: str = "domestic"
    lpg_subsidy_id: str | None = None

    line_1: str | None = None
    line_2: str | None = None
    landmark: str | None = None
    area: str | None = None
    city: str | None = None
    district: str | None = None
    state: str | None = None
    pincode: str | None = None
    address_type: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class RegisterCustomerUseCase:
    def __init__(self, repository: CustomerRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: RegisterCustomerCommand) -> Customer:
        # Check uniqueness of phone
        existing_phone = await self._repository.get_by_phone(command.phone_number)
        if existing_phone is not None:
            msg = f"Customer with phone number {command.phone_number} already exists."
            raise DuplicatePhoneError(msg, phone_number=command.phone_number)

        # Check uniqueness of consumer number (BR-22)
        if command.consumer_number:
            existing_cn = await self._repository.get_by_consumer_number(command.consumer_number)
            if existing_cn is not None:
                msg = f"Customer with consumer number {command.consumer_number} already exists."
                raise DuplicateConsumerNumberError(msg, consumer_number=command.consumer_number)

        # Check uniqueness of the LPG subsidy ID, if supplied
        if command.lpg_subsidy_id is not None:
            existing_lpg = await self._repository.get_by_lpg_subsidy_id(command.lpg_subsidy_id)
            if existing_lpg is not None:
                msg = f"Customer with LPG ID {command.lpg_subsidy_id} already exists."
                raise DuplicateLpgSubsidyIdError(msg, lpg_subsidy_id=command.lpg_subsidy_id)

        customer = Customer(
            customer_id=self._repository.next_id(),
            tenant_id=command.tenant_id,
            branch_id=command.branch_id,
            consumer_number=command.consumer_number,
            full_name=command.full_name,
            phone_number=command.phone_number,
            contact_person=command.contact_person,
            alternate_mobile=command.alternate_mobile,
            email=command.email,
            date_of_birth=command.date_of_birth,
            customer_type=command.customer_type,
            lpg_subsidy_id=command.lpg_subsidy_id,
        )

        if command.line_1:
            customer.add_address(
                line_1=command.line_1,
                line_2=command.line_2,
                landmark=command.landmark,
                area=command.area,
                city=command.city,
                district=command.district,
                state=command.state,
                pincode=command.pincode,
                address_type=command.address_type or "delivery",
                latitude=command.latitude,
                longitude=command.longitude,
            )

        await self._repository.save(customer)
        await self._unit_of_work.commit()
        return customer


@dataclass(frozen=True, slots=True)
class UpdateCustomerProfileCommand(Command):
    customer_id: uuid.UUID
    branch_id: uuid.UUID
    full_name: str
    phone_number: str
    customer_type: str
    status: str
    contact_person: str | None = None
    alternate_mobile: str | None = None
    email: str | None = None
    date_of_birth: datetime.date | None = None
    lpg_subsidy_id: str | None = None


class UpdateCustomerProfileUseCase:
    def __init__(self, repository: CustomerRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: UpdateCustomerProfileCommand) -> Customer:
        customer = await self._repository.get_by_id(command.customer_id)
        if customer is None:
            msg = f"No customer visible with id {command.customer_id}."
            raise NotFoundError(msg, customer_id=str(command.customer_id))

        # Check uniqueness of phone if it has changed
        if customer.phone_number != command.phone_number:
            existing = await self._repository.get_by_phone(command.phone_number)
            if existing is not None and existing.id != customer.id:
                msg = f"Customer with phone number {command.phone_number} already exists."
                raise DuplicatePhoneError(msg, phone_number=command.phone_number)

        # Check uniqueness of the LPG subsidy ID if it has changed
        if command.lpg_subsidy_id is not None and command.lpg_subsidy_id != customer.lpg_subsidy_id:
            existing_lpg = await self._repository.get_by_lpg_subsidy_id(command.lpg_subsidy_id)
            if existing_lpg is not None and existing_lpg.id != customer.id:
                msg = f"Customer with LPG ID {command.lpg_subsidy_id} already exists."
                raise DuplicateLpgSubsidyIdError(msg, lpg_subsidy_id=command.lpg_subsidy_id)

        # Re-initialize to enforce business invariants
        updated = Customer(
            customer_id=customer.id,
            tenant_id=customer.tenant_id,
            branch_id=command.branch_id,
            consumer_number=customer.consumer_number,
            full_name=command.full_name,
            phone_number=command.phone_number,
            contact_person=command.contact_person,
            alternate_mobile=command.alternate_mobile,
            email=command.email,
            date_of_birth=command.date_of_birth,
            customer_type=command.customer_type,
            kyc_status=customer.kyc_status,
            status=command.status,
            lpg_subsidy_id=command.lpg_subsidy_id,
            addresses=customer.addresses,
            kyc_documents=customer.kyc_documents,
            identity_user_id=customer.identity_user_id,
            version=customer.version,
        )

        await self._repository.save(updated)
        await self._unit_of_work.commit()
        return updated


@dataclass(frozen=True, slots=True)
class AddCustomerAddressCommand(Command):
    customer_id: uuid.UUID
    line_1: str
    line_2: str | None = None
    landmark: str | None = None
    area: str | None = None
    city: str | None = None
    district: str | None = None
    state: str | None = None
    pincode: str | None = None
    address_type: str = "delivery"
    latitude: float | None = None
    longitude: float | None = None


class AddCustomerAddressUseCase:
    def __init__(self, repository: CustomerRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: AddCustomerAddressCommand) -> uuid.UUID:
        customer = await self._repository.get_by_id(command.customer_id)
        if customer is None:
            msg = f"No customer visible with id {command.customer_id}."
            raise NotFoundError(msg, customer_id=str(command.customer_id))

        addr_id = customer.add_address(
            line_1=command.line_1,
            line_2=command.line_2,
            landmark=command.landmark,
            area=command.area,
            city=command.city,
            district=command.district,
            state=command.state,
            pincode=command.pincode,
            address_type=command.address_type,
            latitude=command.latitude,
            longitude=command.longitude,
        )

        await self._repository.save(customer)
        await self._unit_of_work.commit()
        return addr_id


@dataclass(frozen=True, slots=True)
class SetPrimaryAddressCommand(Command):
    customer_id: uuid.UUID
    address_id: uuid.UUID


class SetPrimaryAddressUseCase:
    def __init__(self, repository: CustomerRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: SetPrimaryAddressCommand) -> None:
        customer = await self._repository.get_by_id(command.customer_id)
        if customer is None:
            msg = f"No customer visible with id {command.customer_id}."
            raise NotFoundError(msg, customer_id=str(command.customer_id))

        customer.set_primary_address(command.address_id)

        await self._repository.save(customer)
        await self._unit_of_work.commit()


@dataclass(frozen=True, slots=True)
class SubmitKycDocumentCommand(Command):
    customer_id: uuid.UUID
    doc_type: str
    document_number: str
    file_url: str | None = None
    issue_date: datetime.date | None = None
    expiry_date: datetime.date | None = None


class SubmitKycDocumentUseCase:
    def __init__(self, repository: CustomerRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: SubmitKycDocumentCommand) -> uuid.UUID:
        customer = await self._repository.get_by_id(command.customer_id)
        if customer is None:
            msg = f"No customer visible with id {command.customer_id}."
            raise NotFoundError(msg, customer_id=str(command.customer_id))

        doc_id = customer.submit_kyc(
            doc_type=command.doc_type,
            document_number=command.document_number,
            file_url=command.file_url,
            issue_date=command.issue_date,
            expiry_date=command.expiry_date,
        )

        await self._repository.save(customer)
        await self._unit_of_work.commit()
        return doc_id


@dataclass(frozen=True, slots=True)
class VerifyKycDocumentCommand(Command):
    customer_id: uuid.UUID
    doc_id: uuid.UUID
    verified_by: uuid.UUID
    status: str
    rejection_reason: str | None = None


class VerifyKycDocumentUseCase:
    def __init__(self, repository: CustomerRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: VerifyKycDocumentCommand) -> None:
        customer = await self._repository.get_by_id(command.customer_id)
        if customer is None:
            msg = f"No customer visible with id {command.customer_id}."
            raise NotFoundError(msg, customer_id=str(command.customer_id))

        customer.verify_kyc(
            doc_id=command.doc_id,
            verified_by=command.verified_by,
            status=command.status,
            rejection_reason=command.rejection_reason,
        )

        await self._repository.save(customer)
        await self._unit_of_work.commit()


@dataclass(frozen=True, slots=True)
class ApproveCustomerCommand(Command):
    customer_id: uuid.UUID
    approved_by: uuid.UUID
    consumer_number: str | None = None


class ApproveCustomerUseCase:
    def __init__(
        self,
        repository: CustomerRepository,
        sequence: ConsumerNumberSequence,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._sequence = sequence
        self._unit_of_work = unit_of_work

    async def execute(self, command: ApproveCustomerCommand) -> None:
        customer = await self._repository.get_by_id(command.customer_id)
        if customer is None:
            msg = f"No customer visible with id {command.customer_id}."
            raise NotFoundError(msg, customer_id=str(command.customer_id))

        consumer_number = command.consumer_number
        if not consumer_number:
            consumer_number = await self._sequence.next()

        # Check uniqueness of consumer number (BR-22)
        existing_cn = await self._repository.get_by_consumer_number(consumer_number)
        if existing_cn is not None and existing_cn.id != customer.id:
            msg = f"Customer with consumer number {consumer_number} already exists."
            raise DuplicateConsumerNumberError(msg, consumer_number=consumer_number)

        customer.approve(approved_by=command.approved_by, consumer_number=consumer_number)

        await self._repository.save(customer)
        await self._unit_of_work.commit()


@dataclass(frozen=True, slots=True)
class ListCustomersQuery(Query):
    skip: int = 0
    limit: int = 100
    search: str | None = None


@dataclass(frozen=True, slots=True)
class ListCustomersResult:
    items: list[Customer]
    total: int


class ListCustomersUseCase:
    def __init__(self, repository: CustomerRepository) -> None:
        self._repository = repository

    async def execute(self, query: ListCustomersQuery) -> ListCustomersResult:
        items = await self._repository.list_customers(
            skip=query.skip,
            limit=query.limit,
            search=query.search,
        )
        total = await self._repository.count_customers(search=query.search)
        return ListCustomersResult(items=items, total=total)


@dataclass(frozen=True, slots=True)
class GetCustomerQuery(Query):
    customer_id: uuid.UUID


class GetCustomerUseCase:
    def __init__(self, repository: CustomerRepository) -> None:
        self._repository = repository

    async def execute(self, query: GetCustomerQuery) -> Customer | None:
        return await self._repository.get_by_id(query.customer_id)


@dataclass(frozen=True, slots=True)
class GetCustomerByUserIdQuery(Query):
    identity_user_id: uuid.UUID


class GetCustomerByUserIdUseCase:
    def __init__(self, repository: CustomerRepository) -> None:
        self._repository = repository

    async def execute(self, query: GetCustomerByUserIdQuery) -> Customer | None:
        return await self._repository.get_by_identity_user_id(query.identity_user_id)


class PeekNextConsumerNumberUseCase:
    """Suggests the next auto-generated Consumer Number for the register form.

    Advisory only — see `ConsumerNumberSequence`'s docstring. The caller
    remains free to submit a different, manually-entered value.
    """

    def __init__(self, sequence: ConsumerNumberSequence, unit_of_work: UnitOfWork) -> None:
        self._sequence = sequence
        self._unit_of_work = unit_of_work

    async def execute(self) -> str:
        value = await self._sequence.next()
        await self._unit_of_work.commit()
        return value
