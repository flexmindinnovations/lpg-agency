from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from lpg.api.v1.dependencies.customer import (
    get_consumer_number_sequence,
    get_customer_repository,
)
from lpg.api.v1.dependencies.identity import get_current_principal, require_permission, require_permission_or_self
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.api.v1.schemas.customer import (
    AddCustomerAddressRequest,
    CustomerPageResponse,
    CustomerResponse,
    KycDocumentListResponse,
    KycDocumentResponse,
    NextConsumerNumberResponse,
    RegisterCustomerRequest,
    SubmitKycDocumentRequest,
    UpdateCustomerProfileRequest,
    VerifyKycDocumentRequest,
    ApproveCustomerRequest,
)
from lpg.application.common.errors import NotFoundError
from lpg.application.common.ports import UnitOfWork
from lpg.application.customer.ports import ConsumerNumberSequence, CustomerRepository
from lpg.application.customer.use_cases import (
    AddCustomerAddressCommand,
    AddCustomerAddressUseCase,
    GetCustomerQuery,
    GetCustomerUseCase,
    GetCustomerByUserIdQuery,
    GetCustomerByUserIdUseCase,
    ListCustomersQuery,
    ListCustomersUseCase,
    PeekNextConsumerNumberUseCase,
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
    ApproveCustomerCommand,
    ApproveCustomerUseCase,
)
from lpg.application.identity.ports import AuthenticatedPrincipal

router = APIRouter(prefix="/customers", tags=["customers"])


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
            longitude=float(request.longitude) if request.longitude is not None else None,
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
    result = await use_case.execute(ListCustomersQuery(skip=skip, limit=limit, search=search))
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
    customer = await use_case.execute(GetCustomerByUserIdQuery(identity_user_id=principal.user_id))
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
            longitude=float(request.longitude) if request.longitude is not None else None,
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
    await use_case.execute(SetPrimaryAddressCommand(customer_id=customer_id, address_id=address_id))


@router.get(
    "/{customer_id}/kyc",
    response_model=KycDocumentListResponse,
    dependencies=[Depends(require_permission("kyc:read"))],
)
async def list_kyc_documents(
    customer_id: uuid.UUID,
    repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
) -> KycDocumentListResponse:
    use_case = GetCustomerUseCase(repository)
    customer = await use_case.execute(GetCustomerQuery(customer_id=customer_id))
    if customer is None:
        msg = f"No customer visible with id {customer_id}."
        raise NotFoundError(msg, customer_id=str(customer_id))
    return KycDocumentListResponse(
        items=[KycDocumentResponse.model_validate(doc) for doc in customer.kyc_documents]
    )


@router.post(
    "/{customer_id}/kyc",
    response_model=uuid.UUID,
    dependencies=[Depends(require_permission("kyc:manage"))],
)
async def submit_kyc(
    customer_id: uuid.UUID,
    request: SubmitKycDocumentRequest,
    repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> uuid.UUID:
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
) -> None:
    if principal.user_id is None:
        raise HTTPException(status_code=401, detail="User ID is required.")
    use_case = VerifyKycDocumentUseCase(repository, unit_of_work)
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
