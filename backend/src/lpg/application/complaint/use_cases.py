import uuid
from dataclasses import dataclass

from lpg.application.common.ports import TenantResolver
from lpg.application.complaint.ports import ComplaintUnitOfWork
from lpg.domain.complaint.complaint import Complaint
from lpg.domain.complaint.value_objects import (
    ComplaintCategory,
    ComplaintPriority,
    ResolutionOutcome,
)


@dataclass
class RaiseComplaintCommand:
    customer_id: uuid.UUID
    category: ComplaintCategory
    priority: ComplaintPriority
    description: str
    order_id: uuid.UUID | None = None


class RaiseComplaintUseCase:
    def __init__(self, uow: ComplaintUnitOfWork, tenant_resolver: TenantResolver) -> None:
        self._uow = uow
        self._tenant_resolver = tenant_resolver

    async def execute(self, request: object, command: RaiseComplaintCommand) -> uuid.UUID:
        ctx = await self._tenant_resolver.resolve(request)
        if not ctx.user_id:
            raise ValueError("User must be authenticated to raise a complaint")

        complaint = Complaint.create(
            tenant_id=ctx.tenant_id,
            customer_id=command.customer_id,
            category=command.category,
            priority=command.priority,
            description=command.description,
            created_by=ctx.user_id,
            order_id=command.order_id,
        )

        async with self._uow:
            await self._uow.complaints.save(complaint)
            await self._uow.commit()

        return complaint.id


@dataclass
class AssignComplaintCommand:
    complaint_id: uuid.UUID
    assigned_to: uuid.UUID


class AssignComplaintUseCase:
    def __init__(self, uow: ComplaintUnitOfWork, tenant_resolver: TenantResolver) -> None:
        self._uow = uow
        self._tenant_resolver = tenant_resolver

    async def execute(self, request: object, command: AssignComplaintCommand) -> None:
        ctx = await self._tenant_resolver.resolve(request)
        if not ctx.user_id:
            raise ValueError("User must be authenticated to assign a complaint")

        async with self._uow:
            complaint = await self._uow.complaints.get_by_id(ctx.tenant_id, command.complaint_id)
            if not complaint:
                raise ValueError(f"Complaint {command.complaint_id} not found")

            complaint.assign(command.assigned_to, assigned_by=ctx.user_id)
            await self._uow.complaints.save(complaint)
            await self._uow.commit()


@dataclass
class ResolveComplaintCommand:
    complaint_id: uuid.UUID
    outcome: ResolutionOutcome
    resolution_notes: str


class ResolveComplaintUseCase:
    def __init__(self, uow: ComplaintUnitOfWork, tenant_resolver: TenantResolver) -> None:
        self._uow = uow
        self._tenant_resolver = tenant_resolver

    async def execute(self, request: object, command: ResolveComplaintCommand) -> None:
        ctx = await self._tenant_resolver.resolve(request)
        if not ctx.user_id:
            raise ValueError("User must be authenticated to resolve a complaint")

        async with self._uow:
            complaint = await self._uow.complaints.get_by_id(ctx.tenant_id, command.complaint_id)
            if not complaint:
                raise ValueError(f"Complaint {command.complaint_id} not found")

            complaint.resolve(
                outcome=command.outcome,
                resolution_notes=command.resolution_notes,
                resolved_by=ctx.user_id,
            )
            await self._uow.complaints.save(complaint)
            await self._uow.commit()
