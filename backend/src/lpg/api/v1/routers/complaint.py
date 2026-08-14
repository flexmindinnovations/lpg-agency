from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from lpg.api.v1.dependencies.identity import require_permission
from lpg.api.v1.dependencies.complaint import get_complaint_unit_of_work
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
from lpg.infrastructure.persistence.models.complaint import ComplaintModel
from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

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
    # Use the session directly for reads
    assert isinstance(uow._uow, SqlAlchemyUnitOfWork)
    session = uow._uow.session
    
    stmt = (
        select(ComplaintModel)
        .options(selectinload(ComplaintModel.assignments), selectinload(ComplaintModel.resolution))
        .where(ComplaintModel.tenant_id == ctx.tenant_id, ComplaintModel.id == complaint_id)
    )
    result = await session.execute(stmt)
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Complaint not found")
        
    return ComplaintResponse.model_validate(model)

@router.get("", response_model=ComplaintListResponse)
async def list_complaints(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    uow: Annotated[ComplaintUnitOfWork, Depends(get_complaint_unit_of_work)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: str | None = None,
    customer_id: uuid.UUID | None = None,
) -> ComplaintListResponse:
    assert isinstance(uow._uow, SqlAlchemyUnitOfWork)
    session = uow._uow.session
    
    stmt = select(ComplaintModel).where(ComplaintModel.tenant_id == ctx.tenant_id)
    if status:
        stmt = stmt.where(ComplaintModel.status == status)
    if customer_id:
        stmt = stmt.where(ComplaintModel.customer_id == customer_id)
        
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = await session.scalar(count_stmt) or 0
    
    stmt = stmt.order_by(ComplaintModel.created_at.desc()).offset(skip).limit(limit)
    result = await session.execute(stmt)
    items = result.scalars().all()
    
    return ComplaintListResponse(
        items=[ComplaintResponse.model_validate(i) for i in items],
        total=total,
        skip=skip,
        limit=limit
    )
