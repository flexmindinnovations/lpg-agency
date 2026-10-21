from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.errors import AuthenticationError, NotFoundError, ValidationError
from lpg.domain.complaint.complaint import Complaint

if TYPE_CHECKING:
    import uuid

    from lpg.application.common.ports import TenantContext
    from lpg.application.complaint.ports import (
        ComplaintDirectory,
        ComplaintNumberSequence,
        ComplaintUnitOfWork,
    )
    from lpg.domain.complaint.value_objects import (
        ComplaintCategory,
        ComplaintPriority,
        ResolutionOutcome,
    )

from lpg.domain.complaint.value_objects import ComplaintStatus


@dataclass
class RaiseComplaintCommand:
    customer_id: uuid.UUID
    category: ComplaintCategory
    priority: ComplaintPriority
    description: str
    order_id: uuid.UUID | None = None


def _require_user(ctx: TenantContext) -> uuid.UUID:
    if not ctx.user_id:
        msg = "Sign in to work with complaints."
        raise AuthenticationError(msg)
    return ctx.user_id


class RaiseComplaintUseCase:
    """Raise a complaint for a customer that exists in this tenant, and —
    when an order is named — one of that customer's own orders (DO-19).

    `directory` may be left out only by callers that already resolved both
    from the signed-in customer (the WhatsApp assistant)."""

    def __init__(
        self,
        uow: ComplaintUnitOfWork,
        sequence: ComplaintNumberSequence,
        directory: ComplaintDirectory | None = None,
    ) -> None:
        self._uow = uow
        self._sequence = sequence
        self._directory = directory

    async def execute(self, ctx: TenantContext, command: RaiseComplaintCommand) -> uuid.UUID:
        user_id = _require_user(ctx)
        if self._directory is not None:
            await self._ensure_customer_and_order_exist(command)
        complaint_number = await self._sequence.next()
        complaint = Complaint.create(
            tenant_id=ctx.tenant_id,
            customer_id=command.customer_id,
            category=command.category,
            priority=command.priority,
            description=command.description,
            created_by=user_id,
            complaint_number=complaint_number,
            order_id=command.order_id,
        )

        async with self._uow:
            await self._uow.complaints.save(complaint)
            await self._uow.commit()

        return complaint.id

    async def _ensure_customer_and_order_exist(self, command: RaiseComplaintCommand) -> None:
        assert self._directory is not None
        customers = await self._directory.customers([command.customer_id])
        if command.customer_id not in customers:
            msg = "Choose a customer from the list; that customer was not found."
            raise ValidationError(msg, errors={"customer_id": [msg]})
        if command.order_id is not None:
            order = (await self._directory.orders([command.order_id])).get(command.order_id)
            if order is None or order.customer_id != command.customer_id:
                msg = "Choose one of this customer's orders; that order was not found."
                raise ValidationError(msg, errors={"order_id": [msg]})


@dataclass
class AssignComplaintCommand:
    complaint_id: uuid.UUID
    assigned_to: uuid.UUID


class AssignComplaintUseCase:
    """Assign to an active staff member of this tenant who works
    complaints (DO-18) — never an arbitrary id."""

    def __init__(self, uow: ComplaintUnitOfWork, directory: ComplaintDirectory) -> None:
        self._uow = uow
        self._directory = directory

    async def execute(self, ctx: TenantContext, command: AssignComplaintCommand) -> None:
        user_id = _require_user(ctx)
        staff = await self._directory.assignable_staff(ctx.tenant_id)
        if command.assigned_to not in {member.user_id for member in staff}:
            msg = "Choose a staff member from the list; that person cannot take complaints."
            raise ValidationError(msg, errors={"assigned_to": [msg]})

        async with self._uow:
            complaint = await self._uow.complaints.get_by_id(ctx.tenant_id, command.complaint_id)
            if not complaint:
                msg = "Complaint not found."
                raise NotFoundError(msg, complaint_id=str(command.complaint_id))

            complaint.assign(command.assigned_to, assigned_by=user_id)
            await self._uow.complaints.save(complaint)
            await self._uow.commit()


@dataclass
class ResolveComplaintCommand:
    complaint_id: uuid.UUID
    outcome: ResolutionOutcome
    resolution_notes: str


class ResolveComplaintUseCase:
    def __init__(self, uow: ComplaintUnitOfWork) -> None:
        self._uow = uow

    async def execute(self, ctx: TenantContext, command: ResolveComplaintCommand) -> None:
        user_id = _require_user(ctx)

        async with self._uow:
            complaint = await self._uow.complaints.get_by_id(ctx.tenant_id, command.complaint_id)
            if not complaint:
                msg = "Complaint not found."
                raise NotFoundError(msg, complaint_id=str(command.complaint_id))

            complaint.resolve(
                outcome=command.outcome,
                resolution_notes=command.resolution_notes,
                resolved_by=user_id,
            )
            await self._uow.complaints.save(complaint)
            await self._uow.commit()


@dataclass
class GetOpenComplaintsSummaryQuery:
    """Zero-argument — built for the AI Command Center's complaints tool
    (ADR-045). 'Open' means the three non-terminal `ComplaintStatus`
    values (Open/Assigned/InProgress), not a single literal status."""


@dataclass
class OpenComplaintsSummary:
    open_count: int
    assigned_count: int
    in_progress_count: int


class GetOpenComplaintsSummaryUseCase:
    """Read-only — three `count_complaints` calls, one per non-terminal
    status (the repository takes a single status, not a set). No
    `ListComplaintsUseCase` exists yet to wrap; this is new but thin,
    same shape as every other command/use case in this file."""

    def __init__(self, uow: ComplaintUnitOfWork) -> None:
        self._uow = uow

    async def execute(
        self, ctx: TenantContext, query: GetOpenComplaintsSummaryQuery
    ) -> OpenComplaintsSummary:
        _ = query
        async with self._uow:
            open_count = await self._uow.complaints.count_complaints(
                ctx.tenant_id, status=ComplaintStatus.OPEN
            )
            assigned_count = await self._uow.complaints.count_complaints(
                ctx.tenant_id, status=ComplaintStatus.ASSIGNED
            )
            in_progress_count = await self._uow.complaints.count_complaints(
                ctx.tenant_id, status=ComplaintStatus.IN_PROGRESS
            )
        return OpenComplaintsSummary(
            open_count=open_count,
            assigned_count=assigned_count,
            in_progress_count=in_progress_count,
        )
