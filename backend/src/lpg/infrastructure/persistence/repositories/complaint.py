from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from lpg.application.complaint.ports import ComplaintCustomer, ComplaintOrder, StaffMember
from lpg.domain.complaint.complaint import Complaint, ComplaintAssignment, ComplaintResolution
from lpg.domain.complaint.ports import ComplaintRepository
from lpg.domain.complaint.value_objects import (
    ComplaintCategory,
    ComplaintPriority,
    ComplaintStatus,
    ResolutionOutcome,
)
from lpg.infrastructure.persistence.models.complaint import (
    ComplaintAssignmentModel,
    ComplaintModel,
    ComplaintResolutionModel,
)
from lpg.infrastructure.persistence.models.customer import CustomerModel
from lpg.infrastructure.persistence.models.identity import (
    IdentityUserModel,
    IdentityUserPermissionModel,
    PermissionModel,
)
from lpg.infrastructure.persistence.models.order import OrderModel
from lpg.infrastructure.persistence.models.tenant import EmployeeModel

if TYPE_CHECKING:
    from collections.abc import Sequence

    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyComplaintRepository(ComplaintRepository):
    def __init__(self, uow: SqlAlchemyUnitOfWork) -> None:
        self._uow = uow
        self._session = uow.session

    async def save(self, complaint: Complaint) -> None:
        # `AsyncSession`'s identity map holds objects weakly — `get_by_id`'s
        # `model` local goes out of scope and can be collected before this
        # runs, so a bare `session.get()` here (no loader options) may issue
        # a *fresh* fetch that leaves `.assignments`/`.resolution` unloaded.
        # A later plain attribute access on those then triggers an implicit
        # lazy-load outside any greenlet-bridged `await`, raising
        # `MissingGreenlet` — reproducible with a real Postgres session (an
        # in-memory mock never evicts anything, so this never surfaced in a
        # mocked unit test). Passing the same eager-load `options` used by
        # `get_by_id` avoids the implicit lazy-load regardless of whether the
        # identity-map cache hit or missed.
        model = await self._session.get(
            ComplaintModel,
            complaint.id,
            options=(
                selectinload(ComplaintModel.assignments),
                selectinload(ComplaintModel.resolution),
            ),
        )
        if not model:
            model = ComplaintModel(id=complaint.id)
            self._session.add(model)

        model.tenant_id = complaint.tenant_id
        model.complaint_number = complaint.complaint_number
        model.customer_id = complaint.customer_id
        model.order_id = complaint.order_id
        model.category = complaint.category.value
        model.priority = complaint.priority.value
        model.status = complaint.status.value
        model.description = complaint.description
        model.sla_due_at = complaint.sla_due_at
        model.created_at = complaint.created_at
        model.updated_at = complaint.updated_at
        model.created_by = complaint.created_by
        model.updated_by = complaint.updated_by

        # Merge assignments
        existing_assignments = {a.id: a for a in model.assignments}
        model.assignments = []
        for domain_a in complaint.assignments:
            assignment_model = existing_assignments.get(domain_a.id)
            if not assignment_model:
                assignment_model = ComplaintAssignmentModel(
                    id=domain_a.id,
                    tenant_id=domain_a.tenant_id,
                    complaint_id=domain_a.complaint_id,
                    assigned_to=domain_a.assigned_to,
                    assigned_at=domain_a.assigned_at,
                    created_at=domain_a.created_at,
                    created_by=domain_a.created_by,
                )
            model.assignments.append(assignment_model)

        # Merge resolution
        if complaint.resolution:
            domain_r = complaint.resolution
            if not model.resolution:
                model.resolution = ComplaintResolutionModel(
                    id=domain_r.id,
                    tenant_id=domain_r.tenant_id,
                    complaint_id=domain_r.complaint_id,
                )
            model.resolution.outcome = domain_r.outcome.value
            model.resolution.resolution_notes = domain_r.resolution_notes
            model.resolution.resolved_by = domain_r.resolved_by
            model.resolution.resolved_at = domain_r.resolved_at
            model.resolution.created_at = domain_r.created_at
        else:
            model.resolution = None

        # `register_aggregate` is what `SqlAlchemyUnitOfWork.commit()` actually
        # reads (`collect_events()` walks `_tracked_aggregates`) — the
        # previous `session.info["domain_events"]` write here was a second,
        # incompatible mechanism nothing ever read, silently dropping every
        # event `Complaint` recorded (R10, 2026-08-19). `commit()` itself
        # calls `clear_events()` on every tracked aggregate after dispatch,
        # so this method must not clear them first.
        self._uow.register_aggregate(complaint)

    def _to_domain(self, model: ComplaintModel) -> Complaint:
        complaint = Complaint(
            entity_id=model.id,
            tenant_id=model.tenant_id,
            customer_id=model.customer_id,
            order_id=model.order_id,
            complaint_number=model.complaint_number,
            category=ComplaintCategory(model.category),
            priority=ComplaintPriority(model.priority),
            status=ComplaintStatus(model.status),
            description=model.description,
            sla_due_at=model.sla_due_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
            created_by=model.created_by,
            updated_by=model.updated_by,
        )

        complaint.assignments = [
            ComplaintAssignment(
                entity_id=a.id,
                tenant_id=a.tenant_id,
                complaint_id=a.complaint_id,
                assigned_to=a.assigned_to,
                assigned_at=a.assigned_at,
                created_at=a.created_at,
                created_by=a.created_by or uuid.UUID(int=0),
            )
            for a in model.assignments
        ]

        if model.resolution:
            complaint.resolution = ComplaintResolution(
                entity_id=model.resolution.id,
                tenant_id=model.resolution.tenant_id,
                complaint_id=model.resolution.complaint_id,
                outcome=ResolutionOutcome(model.resolution.outcome),
                resolution_notes=model.resolution.resolution_notes,
                resolved_by=model.resolution.resolved_by,
                resolved_at=model.resolution.resolved_at,
                created_at=model.resolution.created_at,
            )

        return complaint

    async def get_by_id(self, tenant_id: uuid.UUID, complaint_id: uuid.UUID) -> Complaint | None:
        stmt = (
            select(ComplaintModel)
            .options(
                selectinload(ComplaintModel.assignments), selectinload(ComplaintModel.resolution)
            )
            .where(ComplaintModel.tenant_id == tenant_id, ComplaintModel.id == complaint_id)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        return self._to_domain(model)

    async def list_complaints(
        self,
        tenant_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 50,
        status: str | None = None,
        customer_id: uuid.UUID | None = None,
    ) -> list[Complaint]:
        stmt = (
            select(ComplaintModel)
            .options(
                selectinload(ComplaintModel.assignments), selectinload(ComplaintModel.resolution)
            )
            .where(ComplaintModel.tenant_id == tenant_id)
        )
        if status:
            stmt = stmt.where(ComplaintModel.status == status)
        if customer_id:
            stmt = stmt.where(ComplaintModel.customer_id == customer_id)

        stmt = stmt.order_by(ComplaintModel.created_at.desc()).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def count_complaints(
        self,
        tenant_id: uuid.UUID,
        *,
        status: str | None = None,
        customer_id: uuid.UUID | None = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(ComplaintModel)
            .where(ComplaintModel.tenant_id == tenant_id)
        )
        if status:
            stmt = stmt.where(ComplaintModel.status == status)
        if customer_id:
            stmt = stmt.where(ComplaintModel.customer_id == customer_id)

        return await self._session.scalar(stmt) or 0


#: Staff who can be handed a complaint; customers and drivers hold
#: `complaints.manage` only to raise and track their own.
_NON_ASSIGNABLE_ROLES = ("customer", "driver")
_COMPLAINTS_PERMISSION = "complaints.manage"


class SqlAlchemyComplaintDirectory:
    """`ComplaintDirectory` over the identity, tenant, customer and orders
    schemas. Read-only."""

    def __init__(self, uow: SqlAlchemyUnitOfWork) -> None:
        self._session = uow.session

    async def assignable_staff(self, tenant_id: uuid.UUID) -> list[StaffMember]:
        has_permission = (
            select(IdentityUserPermissionModel.user_id)
            .join(PermissionModel, PermissionModel.id == IdentityUserPermissionModel.permission_id)
            .where(PermissionModel.code == _COMPLAINTS_PERMISSION)
        )
        stmt = select(IdentityUserModel.id, IdentityUserModel.email, IdentityUserModel.role).where(
            IdentityUserModel.tenant_id == tenant_id,
            IdentityUserModel.is_active.is_(True),
            IdentityUserModel.role.not_in(_NON_ASSIGNABLE_ROLES),
            IdentityUserModel.id.in_(has_permission),
        )
        rows = (await self._session.execute(stmt)).all()
        names = await self._names_by_email(tenant_id, [row.email for row in rows if row.email])
        staff = [
            StaffMember(
                user_id=row.id,
                name=_display_name(row.email, names),
                role=row.role,
                email=row.email,
            )
            for row in rows
        ]
        return sorted(staff, key=lambda member: member.name.lower())

    async def staff_names(
        self, tenant_id: uuid.UUID, user_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, str]:
        if not user_ids:
            return {}
        stmt = select(IdentityUserModel.id, IdentityUserModel.email).where(
            IdentityUserModel.tenant_id == tenant_id, IdentityUserModel.id.in_(set(user_ids))
        )
        rows = (await self._session.execute(stmt)).all()
        names = await self._names_by_email(tenant_id, [row.email for row in rows if row.email])
        return {row.id: _display_name(row.email, names) for row in rows}

    async def customers(
        self, customer_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, ComplaintCustomer]:
        if not customer_ids:
            return {}
        stmt = select(
            CustomerModel.id,
            CustomerModel.full_name,
            CustomerModel.phone_number,
            CustomerModel.consumer_number,
        ).where(CustomerModel.id.in_(set(customer_ids)), CustomerModel.is_deleted.is_(False))
        return {
            row.id: ComplaintCustomer(
                customer_id=row.id,
                full_name=row.full_name,
                phone_number=row.phone_number,
                consumer_number=row.consumer_number,
            )
            for row in (await self._session.execute(stmt)).all()
        }

    async def orders(self, order_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, ComplaintOrder]:
        if not order_ids:
            return {}
        stmt = select(OrderModel.id, OrderModel.order_number, OrderModel.customer_id).where(
            OrderModel.id.in_(set(order_ids)), OrderModel.is_deleted.is_(False)
        )
        return {
            row.id: ComplaintOrder(
                order_id=row.id, order_number=row.order_number, customer_id=row.customer_id
            )
            for row in (await self._session.execute(stmt)).all()
        }

    async def _names_by_email(self, tenant_id: uuid.UUID, emails: Sequence[str]) -> dict[str, str]:
        if not emails:
            return {}
        stmt = select(
            func.lower(EmployeeModel.email), EmployeeModel.first_name, EmployeeModel.last_name
        ).where(
            EmployeeModel.tenant_id == tenant_id,
            EmployeeModel.is_deleted.is_(False),
            func.lower(EmployeeModel.email).in_([email.lower() for email in emails]),
        )
        return {
            email: f"{first} {last}".strip()
            for email, first, last in (await self._session.execute(stmt)).all()
        }


def _display_name(email: str | None, names_by_email: dict[str, str]) -> str:
    """The employee's name when the login matches an employee record,
    otherwise the email address, never an id."""
    if email is None:
        return "Staff member"
    return names_by_email.get(email.lower()) or email
