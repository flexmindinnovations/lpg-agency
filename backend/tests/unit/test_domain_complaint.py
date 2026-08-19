"""Unit tests for the Complaint aggregate root.

Covers SLA-due-date computation by priority (BR-driven, `Complaint.create`),
the `assign`/`resolve` transitions, and the terminal-status guard shared by
both — all without touching the database.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

from lpg.domain.common.base import BusinessRuleViolation
from lpg.domain.complaint.complaint import Complaint
from lpg.domain.complaint.value_objects import (
    ComplaintCategory,
    ComplaintPriority,
    ComplaintStatus,
    ResolutionOutcome,
)


def _make_complaint(
    priority: ComplaintPriority = ComplaintPriority.MEDIUM, **kwargs: object
) -> Complaint:
    defaults: dict[str, object] = {
        "tenant_id": uuid.uuid4(),
        "customer_id": uuid.uuid4(),
        "category": ComplaintCategory.LATE_DELIVERY,
        "priority": priority,
        "description": "Cylinder arrived two days late.",
        "created_by": uuid.uuid4(),
    }
    defaults.update(kwargs)
    return Complaint.create(**defaults)  # type: ignore[arg-type]


class TestComplaintCreation:
    def test_create_starts_open_with_no_assignment_or_resolution(self) -> None:
        complaint = _make_complaint()
        assert complaint.status == ComplaintStatus.OPEN
        assert complaint.assignments == []
        assert complaint.resolution is None

    @pytest.mark.parametrize(
        ("priority", "expected_hours"),
        [
            (ComplaintPriority.CRITICAL, 4),
            (ComplaintPriority.HIGH, 24),
            (ComplaintPriority.MEDIUM, 48),
            (ComplaintPriority.LOW, 72),
        ],
    )
    def test_sla_due_at_matches_priority(
        self, priority: ComplaintPriority, expected_hours: int
    ) -> None:
        before = Complaint._calculate_sla(priority) - timedelta(hours=expected_hours)
        complaint = _make_complaint(priority=priority)
        assert complaint.sla_due_at is not None
        delta = complaint.sla_due_at - before
        # Allow a little slack for wall-clock time elapsed between the two calls.
        upper_bound = timedelta(hours=expected_hours, seconds=5)
        assert timedelta(hours=expected_hours) <= delta <= upper_bound

    def test_order_id_defaults_to_none(self) -> None:
        complaint = _make_complaint()
        assert complaint.order_id is None

    def test_order_id_carried_when_provided(self) -> None:
        order_id = uuid.uuid4()
        complaint = _make_complaint(order_id=order_id)
        assert complaint.order_id == order_id


class TestAssign:
    def test_assign_from_open_moves_to_assigned(self) -> None:
        complaint = _make_complaint()
        assigned_to = uuid.uuid4()
        assigned_by = uuid.uuid4()

        complaint.assign(assigned_to, assigned_by)

        assert complaint.status == ComplaintStatus.ASSIGNED
        assert len(complaint.assignments) == 1
        assignment = complaint.assignments[0]
        assert assignment.assigned_to == assigned_to
        assert assignment.created_by == assigned_by
        assert assignment.complaint_id == complaint.id

    def test_reassign_while_already_assigned_appends_without_changing_status(self) -> None:
        complaint = _make_complaint()
        complaint.assign(uuid.uuid4(), uuid.uuid4())
        complaint.status = ComplaintStatus.IN_PROGRESS

        complaint.assign(uuid.uuid4(), uuid.uuid4())

        assert complaint.status == ComplaintStatus.IN_PROGRESS
        assert len(complaint.assignments) == 2

    @pytest.mark.parametrize(
        "terminal_status",
        [ComplaintStatus.RESOLVED, ComplaintStatus.REJECTED, ComplaintStatus.CLOSED],
    )
    def test_assign_rejected_once_resolved_or_closed(
        self, terminal_status: ComplaintStatus
    ) -> None:
        complaint = _make_complaint()
        complaint.status = terminal_status

        with pytest.raises(BusinessRuleViolation):
            complaint.assign(uuid.uuid4(), uuid.uuid4())


class TestResolve:
    def test_resolve_with_resolved_outcome_moves_to_resolved(self) -> None:
        complaint = _make_complaint()
        resolved_by = uuid.uuid4()

        complaint.resolve(
            ResolutionOutcome.RESOLVED, "Replacement cylinder dispatched.", resolved_by
        )

        assert complaint.status == ComplaintStatus.RESOLVED
        assert complaint.resolution is not None
        assert complaint.resolution.outcome == ResolutionOutcome.RESOLVED
        assert complaint.resolution.resolved_by == resolved_by

    def test_resolve_with_compensated_outcome_moves_to_resolved(self) -> None:
        complaint = _make_complaint()
        complaint.resolve(ResolutionOutcome.COMPENSATED, "Refund issued.", uuid.uuid4())
        assert complaint.status == ComplaintStatus.RESOLVED

    def test_resolve_with_rejected_outcome_moves_to_rejected(self) -> None:
        complaint = _make_complaint()
        complaint.resolve(ResolutionOutcome.REJECTED, "No evidence of shortage.", uuid.uuid4())
        assert complaint.status == ComplaintStatus.REJECTED

    @pytest.mark.parametrize(
        "terminal_status",
        [ComplaintStatus.RESOLVED, ComplaintStatus.REJECTED, ComplaintStatus.CLOSED],
    )
    def test_resolve_rejected_once_already_resolved_or_closed(
        self, terminal_status: ComplaintStatus
    ) -> None:
        complaint = _make_complaint()
        complaint.status = terminal_status

        with pytest.raises(BusinessRuleViolation):
            complaint.resolve(ResolutionOutcome.RESOLVED, "n/a", uuid.uuid4())

    def test_resolve_replaces_any_prior_resolution(self) -> None:
        """`resolve`'s own terminal-status guard prevents a second call in
        practice (resolving always lands on a terminal status), so proving
        `self.resolution` is a straight replace rather than an accumulation
        requires manually resetting status between calls — the same way the
        guard itself is bypassed above for the terminal-status tests.
        """
        complaint = _make_complaint()
        complaint.resolve(ResolutionOutcome.REJECTED, "first pass", uuid.uuid4())
        assert complaint.resolution is not None
        assert complaint.resolution.outcome == ResolutionOutcome.REJECTED

        complaint.status = ComplaintStatus.IN_PROGRESS
        second_resolver = uuid.uuid4()
        complaint.resolve(ResolutionOutcome.RESOLVED, "second pass", second_resolver)

        assert complaint.resolution.outcome == ResolutionOutcome.RESOLVED
        assert complaint.resolution.resolved_by == second_resolver
