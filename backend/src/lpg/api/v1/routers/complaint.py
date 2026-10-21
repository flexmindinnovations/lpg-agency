import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from lpg.api.v1.dependencies.complaint import (
    get_complaint_directory,
    get_complaint_number_sequence,
    get_complaint_unit_of_work,
)
from lpg.api.v1.dependencies.customer import get_customer_repository
from lpg.api.v1.dependencies.identity import get_current_principal, require_permission
from lpg.api.v1.schemas.complaint import (
    AssignComplaintRequest,
    ComplaintAssigneeResponse,
    ComplaintListResponse,
    ComplaintResponse,
    RaiseComplaintRequest,
    ResolveComplaintRequest,
)
from lpg.application.complaint.ports import (
    ComplaintDirectory,
    ComplaintNumberSequence,
    ComplaintUnitOfWork,
)
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
from lpg.domain.complaint.complaint import Complaint
from lpg.domain.complaint.value_objects import ComplaintStatus

router = APIRouter(prefix="/complaints", tags=["Complaints"])


async def _with_names(
    complaints: list[Complaint], directory: ComplaintDirectory, tenant_id: uuid.UUID
) -> list[ComplaintResponse]:
    """Complaint responses with customer, order and assignee names instead
    of bare ids (DO-20) — three lookups for the whole page."""
    customers = await directory.customers([c.customer_id for c in complaints])
    orders = await directory.orders([c.order_id for c in complaints if c.order_id])
    staff = await directory.staff_names(
        tenant_id, [a.assigned_to for c in complaints for a in c.assignments]
    )
    responses = []
    for complaint in complaints:
        response = ComplaintResponse.model_validate(complaint)
        customer = customers.get(complaint.customer_id)
        if customer is not None:
            response.customer_name = customer.full_name
            response.customer_phone = customer.phone_number
            response.consumer_number = customer.consumer_number
        order = orders.get(complaint.order_id) if complaint.order_id else None
        response.order_number = order.order_number if order else None
        for assignment in response.assignments:
            assignment.assigned_to_name = staff.get(assignment.assigned_to)
        if response.assignments:
            latest = max(response.assignments, key=lambda a: a.assigned_at)
            response.assignee_name = latest.assigned_to_name
        responses.append(response)
    return responses


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
    directory: Annotated[ComplaintDirectory, Depends(get_complaint_directory)],
) -> dict[str, uuid.UUID]:
    """Raise a complaint. 422 when the customer, or the order for that
    customer, does not exist. A Gas leak complaint is always Critical."""
    # `complaints.manage` is shared with `customer` for self-service raise —
    # force the caller's own customer_id rather than trusting the request
    # body, or any customer could file a complaint as any other customer.
    customer_id = request.customer_id
    own_customer_id = await _resolve_own_customer_id(principal, customer_repository)
    if own_customer_id is not None:
        customer_id = own_customer_id

    use_case = RaiseComplaintUseCase(uow, complaint_number_sequence, directory)
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
    directory: Annotated[ComplaintDirectory, Depends(get_complaint_directory)],
) -> None:
    """Assign to a staff member from `GET /complaints/assignees`; 422 for
    anyone else, 404 for an unknown complaint, 409 once resolved."""
    await _deny_customers(principal)
    use_case = AssignComplaintUseCase(uow, directory)
    command = AssignComplaintCommand(
        complaint_id=complaint_id,
        assigned_to=request.assigned_to,
    )
    await use_case.execute(principal, command)


@router.post("/{complaint_id}/resolve", status_code=status.HTTP_204_NO_CONTENT)
async def resolve_complaint(
    complaint_id: uuid.UUID,
    request: ResolveComplaintRequest,
    uow: Annotated[ComplaintUnitOfWork, Depends(get_complaint_unit_of_work)],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("complaints.manage"))],
) -> None:
    await _deny_customers(principal)
    use_case = ResolveComplaintUseCase(uow)
    command = ResolveComplaintCommand(
        complaint_id=complaint_id,
        outcome=request.outcome,
        resolution_notes=request.resolution_notes,
    )
    await use_case.execute(principal, command)


async def _deny_customers(principal: AuthenticatedPrincipal) -> None:
    """`complaints.manage` is shared with customers for raising and tracking
    their own complaints; assigning and resolving are staff work."""
    if principal.role == "customer":
        raise HTTPException(status_code=403, detail="Only agency staff can do this.")


@router.get(
    "/assignees",
    response_model=list[ComplaintAssigneeResponse],
    dependencies=[Depends(require_permission("complaints.manage"))],
)
async def list_complaint_assignees(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    directory: Annotated[ComplaintDirectory, Depends(get_complaint_directory)],
) -> list[ComplaintAssigneeResponse]:
    """Active staff of this agency who can take complaints, by name (DO-18)."""
    await _deny_customers(principal)
    return [
        ComplaintAssigneeResponse(
            user_id=member.user_id, name=member.name, role=member.role, email=member.email
        )
        for member in await directory.assignable_staff(principal.tenant_id)
    ]


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
    directory: Annotated[ComplaintDirectory, Depends(get_complaint_directory)],
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

    [response] = await _with_names([complaint], directory, principal.tenant_id)
    return response


@router.get(
    "",
    response_model=ComplaintListResponse,
    dependencies=[Depends(require_permission("complaints.manage"))],
)
async def list_complaints(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    uow: Annotated[ComplaintUnitOfWork, Depends(get_complaint_unit_of_work)],
    customer_repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    directory: Annotated[ComplaintDirectory, Depends(get_complaint_directory)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: ComplaintStatus | None = None,
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
        items=await _with_names(list(items), directory, principal.tenant_id),
        total=total,
        skip=skip,
        limit=limit,
    )
