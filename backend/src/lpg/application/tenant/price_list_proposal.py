"""`AcceptPriceListProposalUseCase` / `RejectPriceListProposalUseCase` /
`ListPendingPriceListProposalsUseCase` — the staff review step of AI
Operational Intelligence, Horizon 1 Stage 3.

**Why accepting doesn't call `SetPriceUseCase`:** that use case commits its
own `UnitOfWork` internally (`application/tenant/price_list.py`) — calling
it from here would split "write the price" and "mark the proposal
accepted" into two separate transactions, so a crash between them would
leave a proposal permanently stuck `accepted` with no matching
`tenant.price_list` row, a real, unrecoverable inconsistency (not a
hypothetical one — this exact commit-splitting failure mode is why
`auto_assign_driver` takes its own transactional care, see that job's own
docstring). `AcceptPriceListProposalUseCase` instead constructs the
`PriceListEntry` directly, in the same transaction as marking the proposal
accepted, and commits once.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command
from lpg.application.common.errors import NotFoundError
from lpg.domain.tenant.price_list import PriceListEntry

if TYPE_CHECKING:
    from lpg.application.common.ports import UnitOfWork
    from lpg.application.tenant.ports import PriceListProposalRepository, PriceListRepository
    from lpg.domain.tenant.price_list_proposal import PriceListProposal


@dataclass(frozen=True, slots=True)
class AcceptPriceListProposalCommand(Command):
    proposal_id: uuid.UUID
    reviewed_by: uuid.UUID


class AcceptPriceListProposalUseCase:
    def __init__(
        self,
        proposal_repository: PriceListProposalRepository,
        price_list_repository: PriceListRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._proposal_repository = proposal_repository
        self._price_list_repository = price_list_repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: AcceptPriceListProposalCommand) -> PriceListEntry:
        proposal = await self._proposal_repository.get(command.proposal_id)
        if proposal is None:
            msg = f"No price list proposal visible with id {command.proposal_id}."
            raise NotFoundError(msg, proposal_id=str(command.proposal_id))

        proposal.accept(reviewed_by=command.reviewed_by)
        await self._proposal_repository.save(proposal)

        entry = PriceListEntry(
            uuid.uuid4(),
            proposal.tenant_id,
            proposal.cylinder_type_id,
            proposal.customer_type,
            proposal.proposed_price,
            proposal.effective_from,
            branch_id=proposal.branch_id,
        )
        await self._price_list_repository.add(entry)
        await self._unit_of_work.commit()
        return entry


@dataclass(frozen=True, slots=True)
class RejectPriceListProposalCommand(Command):
    proposal_id: uuid.UUID
    reviewed_by: uuid.UUID


class RejectPriceListProposalUseCase:
    def __init__(
        self,
        proposal_repository: PriceListProposalRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._proposal_repository = proposal_repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: RejectPriceListProposalCommand) -> None:
        proposal = await self._proposal_repository.get(command.proposal_id)
        if proposal is None:
            msg = f"No price list proposal visible with id {command.proposal_id}."
            raise NotFoundError(msg, proposal_id=str(command.proposal_id))

        proposal.reject(reviewed_by=command.reviewed_by)
        await self._proposal_repository.save(proposal)
        await self._unit_of_work.commit()


@dataclass(frozen=True, slots=True)
class ListPendingPriceListProposalsQuery:
    tenant_id: uuid.UUID


class ListPendingPriceListProposalsUseCase:
    def __init__(self, proposal_repository: PriceListProposalRepository) -> None:
        self._proposal_repository = proposal_repository

    async def execute(self, query: ListPendingPriceListProposalsQuery) -> list[PriceListProposal]:
        return list(await self._proposal_repository.list_pending_for_tenant(query.tenant_id))
