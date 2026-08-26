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
from lpg.domain.customer.kyc_document_parser import parse_kyc_document
from lpg.domain.customer.onboarding_draft import OnboardingDraftEntry

if TYPE_CHECKING:
    import datetime
    import uuid
    from typing import Any

    from lpg.application.accounting.ports import InvoiceRepository
    from lpg.application.common.ports import FileStorage, UnitOfWork
    from lpg.application.customer.ports import (
        ConsumerNumberSequence,
        CustomerRepository,
        DocumentOcrPort,
        OnboardingDraftRepository,
    )


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
class UpdateCustomerAddressCommand(Command):
    customer_id: uuid.UUID
    address_id: uuid.UUID
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


class UpdateCustomerAddressUseCase:
    def __init__(self, repository: CustomerRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: UpdateCustomerAddressCommand) -> None:
        customer = await self._repository.get_by_id(command.customer_id)
        if customer is None:
            msg = f"No customer visible with id {command.customer_id}."
            raise NotFoundError(msg, customer_id=str(command.customer_id))

        customer.update_address(
            address_id=command.address_id,
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
    """Verifying/rejecting a document also drives the customer's overall
    account out of onboarding: the moment every current KYC document is
    verified, this auto-approves the account in the same transaction
    (assigns a consumer number, `status` -> "active") — there was
    previously no separate UI action that ever called the standalone
    approve-customer endpoint, so completing KYC review is what actually
    finishes onboarding for staff in practice. Requires `kyc:manage`
    (the permission gating this endpoint), not `customers:manage` — the
    two are granted together to the roles that handle onboarding today;
    if that ever changes, this auto-approval should move behind its own
    permission check.
    """

    def __init__(
        self,
        repository: CustomerRepository,
        unit_of_work: UnitOfWork,
        sequence: ConsumerNumberSequence,
    ) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work
        self._sequence = sequence

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

        if customer.kyc_status == "verified" and customer.status in (
            "onboarding",
            "pending_approval",
        ):
            consumer_number = await self._sequence.next()
            existing_cn = await self._repository.get_by_consumer_number(consumer_number)
            if existing_cn is not None and existing_cn.id != customer.id:
                msg = f"Customer with consumer number {consumer_number} already exists."
                raise DuplicateConsumerNumberError(msg, consumer_number=consumer_number)
            customer.approve(approved_by=command.verified_by, consumer_number=consumer_number)

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
class CloseCustomerConnectionCommand(Command):
    customer_id: uuid.UUID


class CloseCustomerConnectionUseCase:
    """BR-34 / D-21. `final_ledger_balance` is computed here, from real
    `accounting.invoice` data, then handed to the aggregate — `Customer`
    itself has no visibility into invoices (Clean Architecture layering).
    """

    def __init__(
        self,
        repository: CustomerRepository,
        invoice_repository: InvoiceRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._invoice_repository = invoice_repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: CloseCustomerConnectionCommand) -> None:
        customer = await self._repository.get_by_id(command.customer_id)
        if customer is None:
            msg = f"No customer visible with id {command.customer_id}."
            raise NotFoundError(msg, customer_id=str(command.customer_id))

        final_ledger_balance = await self._invoice_repository.get_outstanding_balance(
            command.customer_id
        )
        customer.close_connection(final_ledger_balance)

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


@dataclass(frozen=True, slots=True)
class SaveOnboardingDraftCommand(Command):
    tenant_id: uuid.UUID
    created_by: uuid.UUID
    current_step: int
    draft_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    registration_data: dict[str, Any] | None = None
    address_data: dict[str, Any] | None = None
    kyc_data: dict[str, Any] | None = None
    kyc_document_blob_ref: str | None = None


class SaveOnboardingDraftUseCase:
    """Create-or-update, scoped to the caller's own draft. Updating someone
    else's `draft_id` (not owned by `created_by`) raises `NotFoundError`
    rather than `PERMISSION_DENIED` — the same "don't leak existence of a
    record you can't see" posture already used by `require_permission_or_self`
    elsewhere in this API layer.
    """

    def __init__(self, repository: OnboardingDraftRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: SaveOnboardingDraftCommand) -> OnboardingDraftEntry:
        existing = None
        if command.draft_id is not None:
            existing = await self._repository.get_by_id(command.draft_id, command.tenant_id)
            if existing is None or existing.created_by != command.created_by:
                msg = f"No draft visible with id {command.draft_id}."
                raise NotFoundError(msg, draft_id=str(command.draft_id))

        draft = OnboardingDraftEntry(
            id=existing.id if existing is not None else self._repository.next_id(),
            tenant_id=command.tenant_id,
            created_by=command.created_by,
            branch_id=command.branch_id,
            current_step=command.current_step,
            registration_data=command.registration_data or {},
            address_data=command.address_data or {},
            kyc_data=command.kyc_data or {},
            kyc_document_blob_ref=command.kyc_document_blob_ref,
        )

        saved = await self._repository.save(draft)
        await self._unit_of_work.commit()
        return saved


@dataclass(frozen=True, slots=True)
class GetOnboardingDraftQuery(Query):
    draft_id: uuid.UUID
    tenant_id: uuid.UUID
    requested_by: uuid.UUID


class GetOnboardingDraftUseCase:
    def __init__(self, repository: OnboardingDraftRepository) -> None:
        self._repository = repository

    async def execute(self, query: GetOnboardingDraftQuery) -> OnboardingDraftEntry | None:
        draft = await self._repository.get_by_id(query.draft_id, query.tenant_id)
        if draft is None or draft.created_by != query.requested_by:
            return None
        return draft


@dataclass(frozen=True, slots=True)
class ListMyOnboardingDraftsQuery(Query):
    tenant_id: uuid.UUID
    created_by: uuid.UUID


class ListMyOnboardingDraftsUseCase:
    def __init__(self, repository: OnboardingDraftRepository) -> None:
        self._repository = repository

    async def execute(self, query: ListMyOnboardingDraftsQuery) -> list[OnboardingDraftEntry]:
        return await self._repository.list_by_user(query.tenant_id, query.created_by)


@dataclass(frozen=True, slots=True)
class DeleteOnboardingDraftCommand(Command):
    draft_id: uuid.UUID
    tenant_id: uuid.UUID
    requested_by: uuid.UUID


class DeleteOnboardingDraftUseCase:
    def __init__(self, repository: OnboardingDraftRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: DeleteOnboardingDraftCommand) -> None:
        existing = await self._repository.get_by_id(command.draft_id, command.tenant_id)
        if existing is None or existing.created_by != command.requested_by:
            msg = f"No draft visible with id {command.draft_id}."
            raise NotFoundError(msg, draft_id=str(command.draft_id))

        await self._repository.delete(command.draft_id, command.tenant_id)
        await self._unit_of_work.commit()


@dataclass(frozen=True, slots=True)
class RecognizeKycDocumentCommand(Command):
    blob_ref: str


@dataclass(frozen=True, slots=True)
class RecognizeKycDocumentResult:
    doc_type: str | None
    document_number: str | None
    full_name: str | None
    date_of_birth: datetime.date | None
    confidence: float
    address_line_1: str | None
    address_line_2: str | None
    address_landmark: str | None
    address_area: str | None
    address_city: str | None
    address_district: str | None
    address_state: str | None
    address_pincode: str | None


class RecognizeKycDocumentUseCase:
    """The backend "second pass": re-runs OCR, server-side, on a document
    image the client already uploaded via `kyc-attachments`, using a
    heavier model than is practical to ship to a browser. Same field-
    parsing logic as the client's own fast first pass
    (`kyc_document_parser.py`, a deliberate port of the TypeScript
    version) — only the OCR engine differs.
    """

    def __init__(self, file_storage: FileStorage, ocr: DocumentOcrPort) -> None:
        self._file_storage = file_storage
        self._ocr = ocr

    async def execute(self, command: RecognizeKycDocumentCommand) -> RecognizeKycDocumentResult:
        image_bytes = await self._file_storage.download(command.blob_ref)
        if image_bytes is None:
            msg = f"No uploaded document found for blob ref {command.blob_ref}."
            raise NotFoundError(msg, blob_ref=command.blob_ref)

        ocr_result = await self._ocr.recognize(image_bytes)
        parsed = parse_kyc_document(ocr_result.text)
        address = parsed.address

        return RecognizeKycDocumentResult(
            doc_type=parsed.doc_type,
            document_number=parsed.document_number,
            full_name=parsed.full_name,
            date_of_birth=parsed.date_of_birth,
            confidence=ocr_result.confidence,
            address_line_1=address.line_1 if address else None,
            address_line_2=address.line_2 if address else None,
            address_landmark=address.landmark if address else None,
            address_area=address.area if address else None,
            address_city=address.city if address else None,
            address_district=address.district if address else None,
            address_state=address.state if address else None,
            address_pincode=address.pincode if address else None,
        )
