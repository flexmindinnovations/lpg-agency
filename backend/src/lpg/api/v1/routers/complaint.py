import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from lpg.api.v1.dependencies.complaint import (
    get_complaint_number_sequence,
    get_complaint_unit_of_work,
)
from lpg.api.v1.dependencies.customer import get_customer_repository
from lpg.api.v1.dependencies.identity import get_current_principal, require_permission
from lpg.api.v1.schemas.complaint import (
    AssignComplaintRequest,
    ComplaintListResponse,
    ComplaintResponse,
    RaiseComplaintRequest,
    ResolveComplaintRequest,
)
from lpg.application.complaint.ports import ComplaintNumberSequence, ComplaintUnitOfWork
from lpg.application.complaint.use_cases import (
    AssignComplaintCommand,
    AssignComplaintUseCase,
    RaiseComplaintCommand,
    RaiseComplaintUseCase,
    ResolveComplaintCommand,
    ResolveComplaintUseCase,
)
from lpg.application.customer.ports import CustomerRepository
from lpg.application.identity.ports import AuthenticatedPrincipal

router = APIRouter(prefix="/complaints", tags=["Complaints"])


async def _resolve_own_customer_id(
    principal: AuthenticatedPrincipal, customer_repository: CustomerRepository
) -> uuid.UUID | None:
    """`complaints.manage` is held by staff *and* `customer` (self-service
    raise/track) -- a `customer` principal must be scoped to their own
    `customer_id`, the same way `order.py`'s `_resolve_scope` and this
    session's ledger/KYC/invoice fixes force it elsewhere, rather than
    trusting a client-supplied `customer_id` (list filter, or the request
    body on `raise_complaint`). `None` means "not a customer, no scoping
    needed"; any other case returns the resolved id or a guaranteed-no-match
    sentinel for an unlinked account.
    """
    if principal.role != "customer":
        return None
    if principal.user_id is None:
        return uuid.UUID(int=0)
    own_customer = await customer_repository.get_by_identity_user_id(principal.user_id)
    return own_customer.id if own_customer else uuid.UUID(int=0)


@router.post("", status_code=status.HTTP_201_CREATED)
async def raise_complaint(
    request: RaiseComplaintRequest,
    uow: Annotated[ComplaintUnitOfWork, Depends(get_complaint_unit_of_work)],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("complaints.manage"))],
    customer_repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    complaint_number_sequence: Annotated[
        ComplaintNumberSequence, Depends(get_complaint_number_sequence)
    ],
) -> dict[str, uuid.UUID]:
    # `complaints.manage` is shared with `customer` for self-service raise —
    # force the caller's own customer_id rather than trusting the request
    # body, or any customer could file a complaint as any other customer.
    customer_id = request.customer_id
    own_customer_id = await _resolve_own_customer_id(principal, customer_repository)
    if own_customer_id is not None:
        customer_id = own_customer_id

    use_case = RaiseComplaintUseCase(uow, complaint_number_sequence)
    command = RaiseComplaintCommand(
        customer_id=customer_id,
        category=request.category,
        priority=request.priority,
        description=request.description,
        order_id=request.order_id,
    )
    complaint_id = await use_case.execute(principal, command)
    return {"id": complaint_id}


@router.post("/{complaint_id}/assign", status_code=status.HTTP_204_NO_CONTENT)
async def assign_complaint(
    complaint_id: uuid.UUID,
    request: AssignComplaintRequest,
    uow: Annotated[ComplaintUnitOfWork, Depends(get_complaint_unit_of_work)],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("complaints.manage"))],
) -> None:
    use_case = AssignComplaintUseCase(uow)
    command = AssignComplaintCommand(
        complaint_id=complaint_id,
        assigned_to=request.assigned_to,
    )
    try:
        await use_case.execute(principal, command)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{complaint_id}/resolve", status_code=status.HTTP_204_NO_CONTENT)
async def resolve_complaint(
    complaint_id: uuid.UUID,
    request: ResolveComplaintRequest,
    uow: Annotated[ComplaintUnitOfWork, Depends(get_complaint_unit_of_work)],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("complaints.manage"))],
) -> None:
    use_case = ResolveComplaintUseCase(uow)
    command = ResolveComplaintCommand(
        complaint_id=complaint_id,
        outcome=request.outcome,
        resolution_notes=request.resolution_notes,
    )
    try:
        await use_case.execute(principal, command)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/{complaint_id}",
    response_model=ComplaintResponse,
    dependencies=[Depends(require_permission("complaints.manage"))],
)
async def get_complaint(
    complaint_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    uow: Annotated[ComplaintUnitOfWork, Depends(get_complaint_unit_of_work)],
    customer_repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
) -> ComplaintResponse:
    complaint = await uow.complaints.get_by_id(principal.tenant_id, complaint_id)
    if complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found")

    own_customer_id = await _resolve_own_customer_id(principal, customer_repository)
    if own_customer_id is not None and complaint.customer_id != own_customer_id:
        # 404, not 403 — matches `_require_own_driver_order`'s documented
        # convention (OWASP API1: never let a caller distinguish "not
        # yours" from "doesn't exist").
        raise HTTPException(status_code=404, detail="Complaint not found")

    return ComplaintResponse.model_validate(complaint)


@router.get(
    "",
    response_model=ComplaintListResponse,
    dependencies=[Depends(require_permission("complaints.manage"))],
)
async def list_complaints(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    uow: Annotated[ComplaintUnitOfWork, Depends(get_complaint_unit_of_work)],
    customer_repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: str | None = None,
    customer_id: uuid.UUID | None = None,
) -> ComplaintListResponse:
    own_customer_id = await _resolve_own_customer_id(principal, customer_repository)
    if own_customer_id is not None:
        customer_id = own_customer_id

    items = await uow.complaints.list_complaints(
        principal.tenant_id, skip=skip, limit=limit, status=status, customer_id=customer_id
    )
    total = await uow.complaints.count_complaints(
        principal.tenant_id, status=status, customer_id=customer_id
    )

    return ComplaintListResponse(
        items=[ComplaintResponse.model_validate(i) for i in items],
        total=total,
        skip=skip,
        limit=limit,
    )
