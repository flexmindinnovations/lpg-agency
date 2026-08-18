import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from lpg.api.v1.dependencies.complaint import get_complaint_unit_of_work
from lpg.api.v1.dependencies.identity import require_permission
from lpg.api.v1.dependencies.tenant import get_tenant_context
from lpg.api.v1.schemas.complaint import (
    AssignComplaintRequest,
    ComplaintListResponse,
    ComplaintResponse,
    RaiseComplaintRequest,
    ResolveComplaintRequest,
)
from lpg.application.common.ports import TenantContext, TenantResolver
from lpg.application.complaint.ports import ComplaintUnitOfWork
from lpg.application.complaint.use_cases import (
    AssignComplaintCommand,
    AssignComplaintUseCase,
    RaiseComplaintCommand,
    RaiseComplaintUseCase,
    ResolveComplaintCommand,
    ResolveComplaintUseCase,
)

router = APIRouter(prefix="/complaints", tags=["Complaints"])

@router.post("", status_code=status.HTTP_201_CREATED)
async def raise_complaint(
    request: RaiseComplaintRequest,
    uow: Annotated[ComplaintUnitOfWork, Depends(get_complaint_unit_of_work)],
    tenant_resolver: Annotated[TenantResolver, Depends(require_permission("complaints.manage"))],
) -> dict[str, uuid.UUID]:
    use_case = RaiseComplaintUseCase(uow, tenant_resolver)
    command = RaiseComplaintCommand(
        customer_id=request.customer_id,
        category=request.category,
        priority=request.priority,
        description=request.description,
        order_id=request.order_id,
    )
    complaint_id = await use_case.execute(request, command)
    return {"id": complaint_id}

@router.post("/{complaint_id}/assign", status_code=status.HTTP_204_NO_CONTENT)
async def assign_complaint(
    complaint_id: uuid.UUID,
    request: AssignComplaintRequest,
    uow: Annotated[ComplaintUnitOfWork, Depends(get_complaint_unit_of_work)],
    tenant_resolver: Annotated[TenantResolver, Depends(require_permission("complaints.manage"))],
) -> None:
    use_case = AssignComplaintUseCase(uow, tenant_resolver)
    command = AssignComplaintCommand(
        complaint_id=complaint_id,
        assigned_to=request.assigned_to,
    )
    try:
        await use_case.execute(request, command)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{complaint_id}/resolve", status_code=status.HTTP_204_NO_CONTENT)
async def resolve_complaint(
    complaint_id: uuid.UUID,
    request: ResolveComplaintRequest,
    uow: Annotated[ComplaintUnitOfWork, Depends(get_complaint_unit_of_work)],
    tenant_resolver: Annotated[TenantResolver, Depends(require_permission("complaints.manage"))],
) -> None:
    use_case = ResolveComplaintUseCase(uow, tenant_resolver)
    command = ResolveComplaintCommand(
        complaint_id=complaint_id,
        outcome=request.outcome,
        resolution_notes=request.resolution_notes,
    )
    try:
        await use_case.execute(request, command)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{complaint_id}", response_model=ComplaintResponse)
async def get_complaint(
    complaint_id: uuid.UUID,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    uow: Annotated[ComplaintUnitOfWork, Depends(get_complaint_unit_of_work)],
) -> ComplaintResponse:
    complaint = await uow.complaints.get_by_id(ctx.tenant_id, complaint_id)
    if complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found")

    return ComplaintResponse.model_validate(complaint)

@router.get("", response_model=ComplaintListResponse)
async def list_complaints(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    uow: Annotated[ComplaintUnitOfWork, Depends(get_complaint_unit_of_work)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: str | None = None,
    customer_id: uuid.UUID | None = None,
) -> ComplaintListResponse:
    items = await uow.complaints.list_complaints(
        ctx.tenant_id, skip=skip, limit=limit, status=status, customer_id=customer_id
    )
    total = await uow.complaints.count_complaints(
        ctx.tenant_id, status=status, customer_id=customer_id
    )

    return ComplaintListResponse(
        items=[ComplaintResponse.model_validate(i) for i in items],
        total=total,
        skip=skip,
        limit=limit,
    )
