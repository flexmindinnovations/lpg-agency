from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from lpg.api.v1.dependencies.accounting import get_invoice_repository
from lpg.api.v1.dependencies.customer import (
    get_consumer_number_sequence,
    get_customer_repository,
    get_document_ocr_port,
)
from lpg.api.v1.dependencies.identity import (
    get_current_principal,
    require_permission,
    require_permission_or_self,
)
from lpg.api.v1.dependencies.order import get_file_storage
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.api.v1.schemas.customer import (
    AddCustomerAddressRequest,
    ApproveCustomerRequest,
    CustomerPageResponse,
    CustomerResponse,
    KycAttachmentResponse,
    KycDocumentListResponse,
    KycDocumentResponse,
    NextConsumerNumberResponse,
    RecognizeKycDocumentRequest,
    RecognizeKycDocumentResponse,
    RegisterCustomerRequest,
    SubmitKycDocumentRequest,
    UpdateCustomerProfileRequest,
    VerifyKycDocumentRequest,
)
from lpg.application.accounting.ports import InvoiceRepository
from lpg.application.common.errors import NotFoundError
from lpg.application.common.ports import FileStorage, UnitOfWork
from lpg.application.customer.ports import (
    ConsumerNumberSequence,
    CustomerRepository,
    DocumentOcrPort,
)
from lpg.application.customer.use_cases import (
    AddCustomerAddressCommand,
    AddCustomerAddressUseCase,
    ApproveCustomerCommand,
    ApproveCustomerUseCase,
    CloseCustomerConnectionCommand,
    CloseCustomerConnectionUseCase,
    GetCustomerByUserIdQuery,
    GetCustomerByUserIdUseCase,
    GetCustomerQuery,
    GetCustomerUseCase,
    ListCustomersQuery,
    ListCustomersUseCase,
    PeekNextConsumerNumberUseCase,
    RecognizeKycDocumentCommand,
    RecognizeKycDocumentUseCase,
    RegisterCustomerCommand,
    RegisterCustomerUseCase,
    SetPrimaryAddressCommand,
    SetPrimaryAddressUseCase,
    SubmitKycDocumentCommand,
    SubmitKycDocumentUseCase,
    UpdateCustomerProfileCommand,
    UpdateCustomerProfileUseCase,
    VerifyKycDocumentCommand,
    VerifyKycDocumentUseCase,
)
from lpg.application.identity.ports import AuthenticatedPrincipal

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.post(
    "/next-consumer-number",
    response_model=NextConsumerNumberResponse,
    dependencies=[Depends(require_permission("customers:create"))],
)
async def peek_next_consumer_number(
    sequence: Annotated[ConsumerNumberSequence, Depends(get_consumer_number_sequence)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> NextConsumerNumberResponse:
    use_case = PeekNextConsumerNumberUseCase(sequence, unit_of_work)
    return NextConsumerNumberResponse(consumer_number=await use_case.execute())


@router.post(
    "",
    response_model=CustomerResponse,
    dependencies=[Depends(require_permission("customers:create"))],
)
async def register_customer(
    request: RegisterCustomerRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> CustomerResponse:
    use_case = RegisterCustomerUseCase(repository, unit_of_work)
    customer = await use_case.execute(
        RegisterCustomerCommand(
            tenant_id=principal.tenant_id,
            branch_id=request.branch_id,
            consumer_number=request.consumer_number,
            full_name=request.full_name,
            phone_number=request.phone_number,
            contact_person=request.contact_person,
            alternate_mobile=request.alternate_mobile,
            email=request.email,
            date_of_birth=request.date_of_birth,
            customer_type=request.customer_type,
            lpg_subsidy_id=request.lpg_subsidy_id,
            line_1=request.line_1,
            line_2=request.line_2,
            landmark=request.landmark,
            area=request.area,
            city=request.city,
            district=request.district,
            state=request.state,
            pincode=request.pincode,
            address_type=request.address_type,
            latitude=float(request.latitude) if request.latitude is not None else None,
            longitude=(
                float(request.longitude) if request.longitude is not None else None
            ),
        )
    )
    return CustomerResponse.model_validate(customer)


@router.get(
    "",
    response_model=CustomerPageResponse,
    dependencies=[Depends(require_permission("customers:read"))],
)
async def list_customers(
    repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
) -> CustomerPageResponse:
    use_case = ListCustomersUseCase(repository)
    result = await use_case.execute(
        ListCustomersQuery(skip=skip, limit=limit, search=search)
    )
    return CustomerPageResponse(
        items=[CustomerResponse.model_validate(c) for c in result.items],
        total=result.total,
    )


@router.get(
    "/me",
    response_model=CustomerResponse,
    summary="Get current customer profile",
)
async def get_my_profile(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
) -> CustomerResponse:
    if not principal.user_id:
        raise HTTPException(status_code=401, detail="User ID missing")
    use_case = GetCustomerByUserIdUseCase(repository)
    customer = await use_case.execute(
        GetCustomerByUserIdQuery(identity_user_id=principal.user_id)
    )
    if customer is None:
        raise NotFoundError("No customer profile found for the current user.")
    return CustomerResponse.model_validate(customer)


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    dependencies=[Depends(require_permission_or_self("customers:read"))],
)
async def get_customer(
    customer_id: uuid.UUID,
    repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
) -> CustomerResponse:
    use_case = GetCustomerUseCase(repository)
    customer = await use_case.execute(GetCustomerQuery(customer_id=customer_id))
    if customer is None:
        msg = f"No customer visible with id {customer_id}."
        raise NotFoundError(msg, customer_id=str(customer_id))
    return CustomerResponse.model_validate(customer)


@router.put(
    "/{customer_id}",
    response_model=CustomerResponse,
    dependencies=[Depends(require_permission_or_self("customers:update"))],
)
async def update_customer_profile(
    customer_id: uuid.UUID,
    request: UpdateCustomerProfileRequest,
    repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> CustomerResponse:
    use_case = UpdateCustomerProfileUseCase(repository, unit_of_work)
    customer = await use_case.execute(
        UpdateCustomerProfileCommand(
            customer_id=customer_id,
            branch_id=request.branch_id,
            full_name=request.full_name,
            phone_number=request.phone_number,
            contact_person=request.contact_person,
            alternate_mobile=request.alternate_mobile,
            email=request.email,
            date_of_birth=request.date_of_birth,
            customer_type=request.customer_type,
            status=request.status,
            lpg_subsidy_id=request.lpg_subsidy_id,
        )
    )
    return CustomerResponse.model_validate(customer)


@router.post(
    "/{customer_id}/addresses",
    response_model=uuid.UUID,
    dependencies=[Depends(require_permission_or_self("customers:update"))],
)
async def add_address(
    customer_id: uuid.UUID,
    request: AddCustomerAddressRequest,
    repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> uuid.UUID:
    use_case = AddCustomerAddressUseCase(repository, unit_of_work)
    return await use_case.execute(
        AddCustomerAddressCommand(
            customer_id=customer_id,
            line_1=request.line_1,
            line_2=request.line_2,
            landmark=request.landmark,
            area=request.area,
            city=request.city,
            district=request.district,
            state=request.state,
            pincode=request.pincode,
            address_type=request.address_type,
            latitude=float(request.latitude) if request.latitude is not None else None,
            longitude=(
                float(request.longitude) if request.longitude is not None else None
            ),
        )
    )


@router.put(
    "/{customer_id}/addresses/{address_id}/primary",
    dependencies=[Depends(require_permission_or_self("customers:update"))],
)
async def set_primary_address(
    customer_id: uuid.UUID,
    address_id: uuid.UUID,
    repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    use_case = SetPrimaryAddressUseCase(repository, unit_of_work)
    await use_case.execute(
        SetPrimaryAddressCommand(customer_id=customer_id, address_id=address_id)
    )


@router.post(
    "/kyc-attachments",
    response_model=KycAttachmentResponse,
    status_code=201,
    dependencies=[Depends(require_permission("kyc:manage"))],
)
async def upload_kyc_attachment(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    file_storage: Annotated[FileStorage, Depends(get_file_storage)],
    file: Annotated[UploadFile, File()],
) -> KycAttachmentResponse:
    """Pre-upload a KYC document image before `POST /{customer_id}/kyc`.

    Deliberately customer-agnostic (staged under a tenant-scoped key, not a
    customer one): during onboarding the wizard runs OCR and lets staff
    review/upload the document image *before* `register_customer` has
    created the `Customer` row that would give this a `customer_id` to key
    off — same reasoning `upload_pod_attachment`
    (`api/v1/routers/order.py`) uses for pre-dispatch blob uploads.
    """
    key = f"tenant/{principal.tenant_id}/kyc-staging/{uuid.uuid4()}_{file.filename}"
    data = await file.read()
    await file_storage.upload(key, data, content_type=file.content_type)
    return KycAttachmentResponse(blob_ref=key)


@router.post(
    "/kyc-attachments/recognize",
    response_model=RecognizeKycDocumentResponse,
    dependencies=[Depends(require_permission("kyc:manage"))],
)
async def recognize_kyc_document(
    request: RecognizeKycDocumentRequest,
    file_storage: Annotated[FileStorage, Depends(get_file_storage)],
    ocr: Annotated[DocumentOcrPort, Depends(get_document_ocr_port)],
) -> RecognizeKycDocumentResponse:
    """The backend OCR "second pass" — re-reads an already-uploaded document
    (`POST /kyc-attachments`) with a heavier, more accurate model than is
    practical to ship to a browser. See `RecognizeKycDocumentUseCase`'s
    docstring for why this exists alongside the client's own OCR pass.
    """
    use_case = RecognizeKycDocumentUseCase(file_storage, ocr)
    result = await use_case.execute(RecognizeKycDocumentCommand(blob_ref=request.blob_ref))
    return RecognizeKycDocumentResponse(
        doc_type=result.doc_type,
        document_number=result.document_number,
        full_name=result.full_name,
        date_of_birth=result.date_of_birth,
        confidence=result.confidence,
        address_line_1=result.address_line_1,
        address_line_2=result.address_line_2,
        address_landmark=result.address_landmark,
        address_area=result.address_area,
        address_city=result.address_city,
        address_district=result.address_district,
        address_state=result.address_state,
        address_pincode=result.address_pincode,
    )


async def _resolve_own_customer_id(
    principal: AuthenticatedPrincipal,
    customer_id: uuid.UUID,
    repository: CustomerRepository,
) -> uuid.UUID:
    """`kyc:read`/`kyc:manage` are held broadly (staff *and* `customer`, for
    self-service) -- a `customer` principal must additionally be scoped to
    their own record, the same way `cylinder_ledger.py`'s `get_ledger`
    forces `customer_id` for a customer's own ledger reads rather than
    trusting whatever the caller passed.
    """
    if principal.role != "customer":
        return customer_id
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="No customer profile linked to this account.")
    own_customer = await repository.get_by_identity_user_id(principal.user_id)
    if own_customer is None or own_customer.id != customer_id:
        raise HTTPException(status_code=403, detail="Cannot access another customer's KYC records.")
    return own_customer.id


@router.get(
    "/{customer_id}/kyc",
    response_model=KycDocumentListResponse,
    dependencies=[Depends(require_permission("kyc:read"))],
)
async def list_kyc_documents(
    customer_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    file_storage: Annotated[FileStorage, Depends(get_file_storage)],
) -> KycDocumentListResponse:
    customer_id = await _resolve_own_customer_id(principal, customer_id, repository)
    use_case = GetCustomerUseCase(repository)
    customer = await use_case.execute(GetCustomerQuery(customer_id=customer_id))
    if customer is None:
        msg = f"No customer visible with id {customer_id}."
        raise NotFoundError(msg, customer_id=str(customer_id))

    items = []
    for doc in customer.kyc_documents:
        response = KycDocumentResponse.model_validate(doc)
        if doc.file_url:
            # `file_url` on the domain object is a raw storage key
            # (`tenant/{tenant_id}/kyc-staging/...`), not a browser-loadable
            # link — resolve it to a short-lived presigned URL at read
            # time, same pattern PrintInvoiceUseCase uses for invoices
            # (`application/printing/use_cases.py`).
            response = response.model_copy(
                update={"file_url": await file_storage.url(doc.file_url)}
            )
        items.append(response)
    return KycDocumentListResponse(items=items)


@router.post(
    "/{customer_id}/kyc",
    response_model=uuid.UUID,
    dependencies=[Depends(require_permission("kyc:manage"))],
)
async def submit_kyc(
    customer_id: uuid.UUID,
    request: SubmitKycDocumentRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> uuid.UUID:
    customer_id = await _resolve_own_customer_id(principal, customer_id, repository)
    use_case = SubmitKycDocumentUseCase(repository, unit_of_work)
    return await use_case.execute(
        SubmitKycDocumentCommand(
            customer_id=customer_id,
            doc_type=request.doc_type,
            document_number=request.document_number,
            file_url=request.file_url,
            issue_date=request.issue_date,
            expiry_date=request.expiry_date,
        )
    )


@router.post(
    "/{customer_id}/kyc/{doc_id}/verify",
    dependencies=[Depends(require_permission("kyc:manage"))],
)
async def verify_kyc(
    customer_id: uuid.UUID,
    doc_id: uuid.UUID,
    request: VerifyKycDocumentRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    sequence: Annotated[ConsumerNumberSequence, Depends(get_consumer_number_sequence)],
) -> None:
    if principal.user_id is None:
        raise HTTPException(status_code=401, detail="User ID is required.")
    # `kyc:manage` is held by `customer` too (self-service upload/submit),
    # but verifying a document is a staff decision by definition — a
    # customer approving/rejecting their own document defeats the point of
    # verification. Block by role, not by withholding the permission code
    # `submit_kyc`/`list_kyc_documents` legitimately share with this.
    if principal.role == "customer":
        raise HTTPException(status_code=403, detail="Customers cannot verify KYC documents.")
    use_case = VerifyKycDocumentUseCase(repository, unit_of_work, sequence)
    await use_case.execute(
        VerifyKycDocumentCommand(
            customer_id=customer_id,
            doc_id=doc_id,
            verified_by=principal.user_id,
            status=request.status,
            rejection_reason=request.rejection_reason,
        )
    )


@router.post(
    "/{customer_id}/approve",
    dependencies=[Depends(require_permission("customers:manage"))],
)
async def approve_customer(
    customer_id: uuid.UUID,
    request: ApproveCustomerRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    sequence: Annotated[ConsumerNumberSequence, Depends(get_consumer_number_sequence)],
    repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    if principal.user_id is None:
        raise HTTPException(status_code=401, detail="User ID is required.")
    use_case = ApproveCustomerUseCase(repository, sequence, unit_of_work)
    await use_case.execute(
        ApproveCustomerCommand(
            customer_id=customer_id,
            approved_by=principal.user_id,
            consumer_number=request.consumer_number,
        )
    )


@router.post(
    "/{customer_id}/close",
    dependencies=[Depends(require_permission("customers:manage"))],
)
async def close_customer_connection(
    customer_id: uuid.UUID,
    repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    invoice_repository: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    """Close a customer's connection for good (BR-34, D-21) — terminal;
    `Customer.change_status` already rejects any transition away from
    `closed`. Same `customers:manage` permission as `/approve`, the other
    significant, staff-only customer lifecycle action.
    """
    use_case = CloseCustomerConnectionUseCase(repository, invoice_repository, unit_of_work)
    await use_case.execute(CloseCustomerConnectionCommand(customer_id=customer_id))
