"""Unit tests for Complaint use cases.

Uses mocked repositories/UoW/tenant-context — no database required.

Each use case takes an already-resolved `TenantContext` directly (matching
`RegisterEmployeeUseCase`'s pattern), not a `TenantResolver` + raw request —
the router already resolves the principal via `require_permission()` before
the use case ever runs.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from lpg.application.complaint.use_cases import (
    AssignComplaintCommand,
    AssignComplaintUseCase,
    RaiseComplaintCommand,
    RaiseComplaintUseCase,
    ResolveComplaintCommand,
    ResolveComplaintUseCase,
)
from lpg.domain.complaint.complaint import Complaint
from lpg.domain.complaint.value_objects import (
    ComplaintCategory,
    ComplaintPriority,
    ComplaintStatus,
    ResolutionOutcome,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_repo() -> MagicMock:
    repo = MagicMock()
    repo.save = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_uow(mock_repo: MagicMock) -> MagicMock:
    uow = MagicMock()
    uow.complaints = mock_repo
    uow.commit = AsyncMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=None)
    return uow


_UNSET = object()


def _make_tenant_context(
    *, tenant_id: uuid.UUID | None = None, user_id: object = _UNSET
) -> MagicMock:
    ctx = MagicMock()
    ctx.tenant_id = tenant_id or uuid.uuid4()
    ctx.user_id = uuid.uuid4() if user_id is _UNSET else user_id
    return ctx


def _make_complaint(**kwargs: object) -> Complaint:
    defaults: dict[str, object] = {
        "tenant_id": uuid.uuid4(),
        "customer_id": uuid.uuid4(),
        "category": ComplaintCategory.OTHER,
        "priority": ComplaintPriority.MEDIUM,
        "description": "test complaint",
        "created_by": uuid.uuid4(),
        "complaint_number": "CMP000001",
    }
    defaults.update(kwargs)
    return Complaint.create(**defaults)  # type: ignore[arg-type]


@pytest.fixture
def mock_complaint_number_sequence() -> MagicMock:
    sequence = MagicMock()
    sequence.next = AsyncMock(return_value="CMP000001")
    return sequence


# ---------------------------------------------------------------------------
# RaiseComplaintUseCase
# ---------------------------------------------------------------------------


class TestRaiseComplaintUseCase:
    async def test_raises_complaint_and_saves(
        self,
        mock_uow: MagicMock,
        mock_repo: MagicMock,
        mock_complaint_number_sequence: MagicMock,
    ) -> None:
        command = RaiseComplaintCommand(
            customer_id=uuid.uuid4(),
            category=ComplaintCategory.LATE_DELIVERY,
            priority=ComplaintPriority.HIGH,
            description="Two hours late.",
        )
        use_case = RaiseComplaintUseCase(mock_uow, mock_complaint_number_sequence)

        complaint_id = await use_case.execute(_make_tenant_context(), command)

        mock_repo.save.assert_called_once()
        saved: Complaint = mock_repo.save.call_args[0][0]
        assert saved.id == complaint_id
        assert saved.category == ComplaintCategory.LATE_DELIVERY
        assert saved.priority == ComplaintPriority.HIGH
        mock_uow.commit.assert_called_once()

    async def test_rejects_unauthenticated_request(
        self, mock_uow: MagicMock, mock_complaint_number_sequence: MagicMock
    ) -> None:
        command = RaiseComplaintCommand(
            customer_id=uuid.uuid4(),
            category=ComplaintCategory.OTHER,
            priority=ComplaintPriority.LOW,
            description="n/a",
        )
        use_case = RaiseComplaintUseCase(mock_uow, mock_complaint_number_sequence)

        with pytest.raises(ValueError, match="authenticated"):
            await use_case.execute(_make_tenant_context(user_id=None), command)

        mock_uow.commit.assert_not_called()


# ---------------------------------------------------------------------------
# AssignComplaintUseCase
# ---------------------------------------------------------------------------


class TestAssignComplaintUseCase:
    async def test_assigns_and_saves(self, mock_uow: MagicMock, mock_repo: MagicMock) -> None:
        complaint = _make_complaint()
        mock_repo.get_by_id = AsyncMock(return_value=complaint)
        assigned_to = uuid.uuid4()
        command = AssignComplaintCommand(complaint_id=complaint.id, assigned_to=assigned_to)

        use_case = AssignComplaintUseCase(mock_uow)
        await use_case.execute(_make_tenant_context(), command)

        assert complaint.status == ComplaintStatus.ASSIGNED
        assert complaint.assignments[0].assigned_to == assigned_to
        mock_repo.save.assert_called_once_with(complaint)
        mock_uow.commit.assert_called_once()

    async def test_raises_when_complaint_not_found(
        self, mock_uow: MagicMock, mock_repo: MagicMock
    ) -> None:
        mock_repo.get_by_id = AsyncMock(return_value=None)
        command = AssignComplaintCommand(complaint_id=uuid.uuid4(), assigned_to=uuid.uuid4())
        use_case = AssignComplaintUseCase(mock_uow)

        with pytest.raises(ValueError, match="not found"):
            await use_case.execute(_make_tenant_context(), command)

        mock_repo.save.assert_not_called()
        mock_uow.commit.assert_not_called()

    async def test_rejects_unauthenticated_request(self, mock_uow: MagicMock) -> None:
        command = AssignComplaintCommand(complaint_id=uuid.uuid4(), assigned_to=uuid.uuid4())
        use_case = AssignComplaintUseCase(mock_uow)

        with pytest.raises(ValueError, match="authenticated"):
            await use_case.execute(_make_tenant_context(user_id=None), command)


# ---------------------------------------------------------------------------
# ResolveComplaintUseCase
# ---------------------------------------------------------------------------


class TestResolveComplaintUseCase:
    async def test_resolves_and_saves(self, mock_uow: MagicMock, mock_repo: MagicMock) -> None:
        complaint = _make_complaint()
        mock_repo.get_by_id = AsyncMock(return_value=complaint)
        command = ResolveComplaintCommand(
            complaint_id=complaint.id,
            outcome=ResolutionOutcome.RESOLVED,
            resolution_notes="Refund processed.",
        )

        use_case = ResolveComplaintUseCase(mock_uow)
        await use_case.execute(_make_tenant_context(), command)

        assert complaint.status == ComplaintStatus.RESOLVED
        assert complaint.resolution is not None
        assert complaint.resolution.resolution_notes == "Refund processed."
        mock_repo.save.assert_called_once_with(complaint)
        mock_uow.commit.assert_called_once()

    async def test_rejected_outcome_moves_to_rejected(
        self, mock_uow: MagicMock, mock_repo: MagicMock
    ) -> None:
        complaint = _make_complaint()
        mock_repo.get_by_id = AsyncMock(return_value=complaint)
        command = ResolveComplaintCommand(
            complaint_id=complaint.id,
            outcome=ResolutionOutcome.REJECTED,
            resolution_notes="No evidence.",
        )

        use_case = ResolveComplaintUseCase(mock_uow)
        await use_case.execute(_make_tenant_context(), command)

        assert complaint.status == ComplaintStatus.REJECTED

    async def test_raises_when_complaint_not_found(
        self, mock_uow: MagicMock, mock_repo: MagicMock
    ) -> None:
        mock_repo.get_by_id = AsyncMock(return_value=None)
        command = ResolveComplaintCommand(
            complaint_id=uuid.uuid4(),
            outcome=ResolutionOutcome.RESOLVED,
            resolution_notes="n/a",
        )
        use_case = ResolveComplaintUseCase(mock_uow)

        with pytest.raises(ValueError, match="not found"):
            await use_case.execute(_make_tenant_context(), command)

        mock_repo.save.assert_not_called()
