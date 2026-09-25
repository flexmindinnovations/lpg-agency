"""Unit tests for `AcceptPriceListProposalUseCase` / `RejectPriceListProposalUseCase`
/ `ListPendingPriceListProposalsUseCase` (AI Operational Intelligence,
Horizon 1 Stage 3). Fake repositories, no DB.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from lpg.application.common.errors import NotFoundError
from lpg.application.tenant.price_list_proposal import (
    AcceptPriceListProposalCommand,
    AcceptPriceListProposalUseCase,
    ListPendingPriceListProposalsQuery,
    ListPendingPriceListProposalsUseCase,
    RejectPriceListProposalCommand,
    RejectPriceListProposalUseCase,
)
from lpg.domain.tenant.price_list_proposal import PriceListProposal

if TYPE_CHECKING:
    from collections.abc import Sequence

    from lpg.domain.common.base import DomainEvent
    from lpg.domain.tenant.price_list import PriceListEntry


class _FakeUnitOfWork:
    def __init__(self) -> None:
        self.commits = 0

    async def __aenter__(self) -> _FakeUnitOfWork:
        return self

    async def __aexit__(self, *_: object) -> None:
        pass

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        pass

    def collect_events(self) -> Sequence[DomainEvent]:
        return []


class _FakePriceListProposalRepository:
    def __init__(self, proposals: dict[uuid.UUID, PriceListProposal]) -> None:
        self._proposals = proposals
        self.saved: list[PriceListProposal] = []

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    async def add_ignoring_conflicts(self, proposals: list[PriceListProposal]) -> int:
        raise NotImplementedError

    async def get(self, proposal_id: uuid.UUID) -> PriceListProposal | None:
        return self._proposals.get(proposal_id)

    async def list_pending_for_tenant(self, tenant_id: uuid.UUID) -> list[PriceListProposal]:
        return [p for p in self._proposals.values() if p.tenant_id == tenant_id]

    async def save(self, proposal: PriceListProposal) -> None:
        self.saved.append(proposal)
        self._proposals[proposal.id] = proposal


class _FakePriceListRepository:
    def __init__(self) -> None:
        self.added: list[PriceListEntry] = []

    async def list_for_tenant_and_cylinder_type(
        self, tenant_id: uuid.UUID, cylinder_type_id: uuid.UUID, customer_type: str
    ) -> list[PriceListEntry]:
        raise NotImplementedError

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> list[PriceListEntry]:
        raise NotImplementedError

    async def add(self, entry: PriceListEntry) -> None:
        self.added.append(entry)


def _pending_proposal(*, tenant_id: uuid.UUID | None = None) -> PriceListProposal:
    return PriceListProposal(
        uuid.uuid4(),
        tenant_id or uuid.uuid4(),
        uuid.uuid4(),
        "domestic",
        Decimal("950.00"),
        datetime(2026, 10, 1, tzinfo=UTC),
        "https://example.com/rates",
        datetime(2026, 9, 12, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_accept_writes_a_price_list_entry_and_marks_accepted() -> None:
    proposal = _pending_proposal()
    proposal_repo = _FakePriceListProposalRepository({proposal.id: proposal})
    price_list_repo = _FakePriceListRepository()
    uow = _FakeUnitOfWork()
    reviewer = uuid.uuid4()

    entry = await AcceptPriceListProposalUseCase(proposal_repo, price_list_repo, uow).execute(
        AcceptPriceListProposalCommand(proposal_id=proposal.id, reviewed_by=reviewer)
    )

    assert entry.tenant_id == proposal.tenant_id
    assert entry.cylinder_type_id == proposal.cylinder_type_id
    assert entry.customer_type == proposal.customer_type
    assert entry.price == proposal.proposed_price
    assert entry.effective_from == proposal.effective_from
    assert len(price_list_repo.added) == 1

    saved = proposal_repo.saved[0]
    assert saved.status == "accepted"
    assert saved.reviewed_by == reviewer
    assert uow.commits == 1


@pytest.mark.asyncio
async def test_accept_raises_not_found_for_an_unknown_proposal() -> None:
    proposal_repo = _FakePriceListProposalRepository({})
    price_list_repo = _FakePriceListRepository()
    uow = _FakeUnitOfWork()

    with pytest.raises(NotFoundError):
        await AcceptPriceListProposalUseCase(proposal_repo, price_list_repo, uow).execute(
            AcceptPriceListProposalCommand(proposal_id=uuid.uuid4(), reviewed_by=uuid.uuid4())
        )
    assert price_list_repo.added == []


@pytest.mark.asyncio
async def test_reject_marks_rejected_without_writing_a_price() -> None:
    proposal = _pending_proposal()
    proposal_repo = _FakePriceListProposalRepository({proposal.id: proposal})
    uow = _FakeUnitOfWork()
    reviewer = uuid.uuid4()

    await RejectPriceListProposalUseCase(proposal_repo, uow).execute(
        RejectPriceListProposalCommand(proposal_id=proposal.id, reviewed_by=reviewer)
    )

    saved = proposal_repo.saved[0]
    assert saved.status == "rejected"
    assert saved.reviewed_by == reviewer
    assert uow.commits == 1


@pytest.mark.asyncio
async def test_list_pending_scopes_to_tenant() -> None:
    tenant_id = uuid.uuid4()
    mine = _pending_proposal(tenant_id=tenant_id)
    someone_elses = _pending_proposal()
    proposal_repo = _FakePriceListProposalRepository(
        {mine.id: mine, someone_elses.id: someone_elses}
    )

    results = await ListPendingPriceListProposalsUseCase(proposal_repo).execute(
        ListPendingPriceListProposalsQuery(tenant_id=tenant_id)
    )

    assert [p.id for p in results] == [mine.id]
