"""`PriceListProposal` — an OMC-sourced (or manually staged) price change
awaiting staff review (AI Operational Intelligence, Horizon 1 Stage 3).

Unlike `PriceListEntry` (append-only — "changing" a price always inserts
a new historized row), a proposal is a real review-queue row: its
`status` moves `pending` → `accepted` or `pending` → `rejected` exactly
once, in place. Accepting one does **not** itself write to
`tenant.price_list` — `AcceptPriceListProposalUseCase`
(`application/tenant/price_list_proposal.py`) does that as part of the
same transaction, so the append-only price history still has exactly one
write path, just as `SetPriceUseCase` intends.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from lpg.domain.common.base import AggregateRoot, InvariantViolation
from lpg.domain.tenant.price_list import CUSTOMER_TYPES

if TYPE_CHECKING:
    import uuid
    from decimal import Decimal

STATUSES = frozenset({"pending", "accepted", "rejected"})


class PriceListProposal(AggregateRoot):
    __slots__ = (
        "_branch_id",
        "_customer_type",
        "_cylinder_type_id",
        "_effective_from",
        "_fetched_at",
        "_proposed_price",
        "_reviewed_at",
        "_reviewed_by",
        "_source_url",
        "_status",
        "_tenant_id",
    )

    def __init__(
        self,
        proposal_id: uuid.UUID,
        tenant_id: uuid.UUID,
        cylinder_type_id: uuid.UUID,
        customer_type: str,
        proposed_price: Decimal,
        effective_from: datetime,
        source_url: str,
        fetched_at: datetime,
        *,
        branch_id: uuid.UUID | None = None,
        status: str = "pending",
        reviewed_by: uuid.UUID | None = None,
        reviewed_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(proposal_id, version=version)
        if customer_type not in CUSTOMER_TYPES:
            msg = f"'{customer_type}' is not a recognized customer type."
            raise InvariantViolation(msg, customer_type=customer_type)
        if proposed_price <= 0:
            msg = "Proposed price must be greater than zero."
            raise InvariantViolation(msg, proposed_price=str(proposed_price))
        if status not in STATUSES:
            msg = f"'{status}' is not a recognized proposal status."
            raise InvariantViolation(msg, status=status)

        self._tenant_id = tenant_id
        self._cylinder_type_id = cylinder_type_id
        self._customer_type = customer_type
        self._branch_id = branch_id
        self._proposed_price = proposed_price
        self._effective_from = effective_from
        self._source_url = source_url
        self._fetched_at = fetched_at
        self._status = status
        self._reviewed_by = reviewed_by
        self._reviewed_at = reviewed_at

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._tenant_id

    @property
    def cylinder_type_id(self) -> uuid.UUID:
        return self._cylinder_type_id

    @property
    def customer_type(self) -> str:
        return self._customer_type

    @property
    def branch_id(self) -> uuid.UUID | None:
        return self._branch_id

    @property
    def proposed_price(self) -> Decimal:
        return self._proposed_price

    @property
    def effective_from(self) -> datetime:
        return self._effective_from

    @property
    def source_url(self) -> str:
        return self._source_url

    @property
    def fetched_at(self) -> datetime:
        return self._fetched_at

    @property
    def status(self) -> str:
        return self._status

    @property
    def reviewed_by(self) -> uuid.UUID | None:
        return self._reviewed_by

    @property
    def reviewed_at(self) -> datetime | None:
        return self._reviewed_at

    def accept(self, *, reviewed_by: uuid.UUID) -> None:
        """Marks this proposal accepted. Does not itself write to
        `tenant.price_list` — the use case does that, in the same
        transaction, using this proposal's own dimension/price/
        effective_from."""
        if self._status != "pending":
            msg = f"Only a pending proposal can be accepted (status is '{self._status}')."
            raise InvariantViolation(msg, proposal_id=str(self.id), status=self._status)
        self._status = "accepted"
        self._reviewed_by = reviewed_by
        self._reviewed_at = datetime.now(UTC)

    def reject(self, *, reviewed_by: uuid.UUID) -> None:
        if self._status != "pending":
            msg = f"Only a pending proposal can be rejected (status is '{self._status}')."
            raise InvariantViolation(msg, proposal_id=str(self.id), status=self._status)
        self._status = "rejected"
        self._reviewed_by = reviewed_by
        self._reviewed_at = datetime.now(UTC)
