import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from lpg.domain.common.base import AggregateRoot, DomainEvent, Entity
from lpg.domain.complaint.value_objects import (
    ComplaintCategory,
    ComplaintPriority,
    ComplaintStatus,
    ResolutionOutcome,
)

# ---------------------------------------------------------------------------
# Domain Events
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ComplaintRaised(DomainEvent):
    """Fired when a complaint is raised (BR-33)."""

    complaint_id: uuid.UUID
    tenant_id: uuid.UUID
    customer_id: uuid.UUID
    category: ComplaintCategory
    priority: ComplaintPriority
    sla_due_at: datetime


@dataclass(frozen=True, slots=True)
class ComplaintResolved(DomainEvent):
    """Fired when a complaint reaches a terminal outcome — resolved,
    compensated, or rejected (D-20). `outcome` distinguishes which.
    """

    complaint_id: uuid.UUID
    tenant_id: uuid.UUID
    outcome: ResolutionOutcome
    resolved_by: uuid.UUID
    resolved_at: datetime


@dataclass
class ComplaintAssignment(Entity):
    """`@dataclass` generates its own `__init__` from these fields, which
    never calls `Entity.__init__` nor sets its `_id` slot — `entity_id` is
    the real, populated field. `.id` is overridden below to read it instead
    of `Entity.id`'s `self._id`, which would otherwise raise `AttributeError`
    on every access (it did: this broke `save()`'s assignment-merge lookup
    and `ComplaintAssignmentResponse` serialization alike, on any complaint
    with at least one assignment, until covered by R7's test suite).
    """

    entity_id: uuid.UUID
    tenant_id: uuid.UUID
    complaint_id: uuid.UUID
    assigned_to: uuid.UUID
    assigned_at: datetime
    created_at: datetime
    created_by: uuid.UUID

    @property
    def id(self) -> uuid.UUID:
        return self.entity_id


@dataclass
class ComplaintResolution(Entity):
    """See `ComplaintAssignment`'s docstring — same `entity_id`-vs-`.id` gap,
    same fix.
    """

    entity_id: uuid.UUID
    tenant_id: uuid.UUID
    complaint_id: uuid.UUID
    outcome: ResolutionOutcome
    resolution_notes: str
    resolved_by: uuid.UUID
    resolved_at: datetime
    created_at: datetime

    @property
    def id(self) -> uuid.UUID:
        return self.entity_id


class Complaint(AggregateRoot):
    def __init__(
        self,
        entity_id: uuid.UUID,
        tenant_id: uuid.UUID,
        customer_id: uuid.UUID,
        category: ComplaintCategory,
        priority: ComplaintPriority,
        description: str,
        status: ComplaintStatus = ComplaintStatus.OPEN,
        order_id: uuid.UUID | None = None,
        sla_due_at: datetime | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        created_by: uuid.UUID | None = None,
        updated_by: uuid.UUID | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(entity_id, version=version)
        self.tenant_id = tenant_id
        self.customer_id = customer_id
        self.order_id = order_id
        self.category = category
        self.priority = priority
        self.status = status
        self.description = description
        self.sla_due_at = sla_due_at

        now = datetime.now(UTC)
        self.created_at = created_at or now
        self.updated_at = updated_at or now
        self.created_by = created_by
        self.updated_by = updated_by

        self.assignments: list[ComplaintAssignment] = []
        self.resolution: ComplaintResolution | None = None

    @classmethod
    def create(
        cls,
        tenant_id: uuid.UUID,
        customer_id: uuid.UUID,
        category: ComplaintCategory,
        priority: ComplaintPriority,
        description: str,
        created_by: uuid.UUID,
        order_id: uuid.UUID | None = None,
    ) -> "Complaint":
        # Calculate SLA Due At based on priority
        sla_due_at = cls._calculate_sla(priority)

        complaint = cls(
            entity_id=uuid.uuid4(),
            tenant_id=tenant_id,
            customer_id=customer_id,
            category=category,
            priority=priority,
            description=description,
            order_id=order_id,
            sla_due_at=sla_due_at,
            created_by=created_by,
            updated_by=created_by,
        )
        complaint.record_event(
            ComplaintRaised(
                complaint_id=complaint.id,
                tenant_id=tenant_id,
                customer_id=customer_id,
                category=category,
                priority=priority,
                sla_due_at=sla_due_at,
            )
        )
        return complaint

    @staticmethod
    def _calculate_sla(priority: ComplaintPriority) -> datetime:
        from datetime import timedelta

        now = datetime.now(UTC)
        if priority == ComplaintPriority.CRITICAL:
            return now + timedelta(hours=4)
        elif priority == ComplaintPriority.HIGH:
            return now + timedelta(hours=24)
        elif priority == ComplaintPriority.MEDIUM:
            return now + timedelta(hours=48)
        else:
            return now + timedelta(hours=72)

    def assign(self, assigned_to: uuid.UUID, assigned_by: uuid.UUID) -> None:
        from lpg.domain.common.base import BusinessRuleViolation

        if self.status in [
            ComplaintStatus.RESOLVED,
            ComplaintStatus.REJECTED,
            ComplaintStatus.CLOSED,
        ]:
            raise BusinessRuleViolation("Cannot assign a complaint that is resolved or closed")

        now = datetime.now(UTC)
        assignment = ComplaintAssignment(
            entity_id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            complaint_id=self.id,
            assigned_to=assigned_to,
            assigned_at=now,
            created_at=now,
            created_by=assigned_by,
        )
        self.assignments.append(assignment)

        # If it's the first assignment or the complaint is still open, move to ASSIGNED
        if self.status == ComplaintStatus.OPEN:
            self.status = ComplaintStatus.ASSIGNED

        self.updated_at = now
        self.updated_by = assigned_by

    def resolve(
        self,
        outcome: ResolutionOutcome,
        resolution_notes: str,
        resolved_by: uuid.UUID,
    ) -> None:
        from lpg.domain.common.base import BusinessRuleViolation

        if self.status in [
            ComplaintStatus.RESOLVED,
            ComplaintStatus.REJECTED,
            ComplaintStatus.CLOSED,
        ]:
            raise BusinessRuleViolation("Complaint is already resolved or closed")

        now = datetime.now(UTC)
        resolution = ComplaintResolution(
            entity_id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            complaint_id=self.id,
            outcome=outcome,
            resolution_notes=resolution_notes,
            resolved_by=resolved_by,
            resolved_at=now,
            created_at=now,
        )
        self.resolution = resolution

        if outcome == ResolutionOutcome.REJECTED:
            self.status = ComplaintStatus.REJECTED
        else:
            self.status = ComplaintStatus.RESOLVED

        self.updated_at = now
        self.updated_by = resolved_by

        self.record_event(
            ComplaintResolved(
                complaint_id=self.id,
                tenant_id=self.tenant_id,
                outcome=outcome,
                resolved_by=resolved_by,
                resolved_at=now,
            )
        )
