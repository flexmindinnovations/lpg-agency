"""`CreditNote` aggregate root.

A refund request and approval, tracked as its own aggregate rather than
nested inside `Invoice` — the request and the approval are two separate
HTTP requests, often by two different actors, the same reasoning
`domain/order/order.py`'s `CancellationRecord` is a standalone thing rather
than an in-aggregate pending record (BR-20).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from lpg.domain.common.base import AggregateRoot, DomainEvent, InvariantViolation

if TYPE_CHECKING:
    import uuid


# ---------------------------------------------------------------------------
# Domain Events
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RefundApproved(DomainEvent):
    """Fired only on approval (BR-20) — a merely-requested credit note is
    not yet a fact anything downstream should react to.
    """

    credit_note_id: uuid.UUID
    tenant_id: uuid.UUID
    invoice_id: uuid.UUID
    amount: Decimal
    approved_by: uuid.UUID


# ---------------------------------------------------------------------------
# Aggregate Root
# ---------------------------------------------------------------------------


class CreditNote(AggregateRoot):
    """`amount` is validated by the requesting use case against the
    invoice's actual `amount_paid` (this aggregate has no visibility into
    `Invoice`) — never here.
    """

    __slots__ = (
        "_amount",
        "_approved_at",
        "_approved_by",
        "_invoice_id",
        "_reason",
        "_requested_at",
        "_requested_by",
        "_tenant_id",
    )

    def __init__(
        self,
        *,
        credit_note_id: uuid.UUID,
        tenant_id: uuid.UUID,
        invoice_id: uuid.UUID,
        amount: Decimal,
        reason: str,
        requested_by: uuid.UUID,
        requested_at: datetime | None = None,
        approved_by: uuid.UUID | None = None,
        approved_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(credit_note_id, version=version)
        if amount <= Decimal("0"):
            msg = f"Credit note amount must be > 0, got {amount}."
            raise InvariantViolation(msg)
        if not reason.strip():
            msg = "Credit note reason must not be empty."
            raise InvariantViolation(msg)
        if (approved_by is None) != (approved_at is None):
            msg = "approved_by and approved_at must both be set, or both be None."
            raise InvariantViolation(msg)

        self._tenant_id = tenant_id
        self._invoice_id = invoice_id
        self._amount = amount
        self._reason = reason
        self._requested_by = requested_by
        self._requested_at = requested_at or datetime.now(UTC)
        self._approved_by = approved_by
        self._approved_at = approved_at

    @classmethod
    def request(
        cls,
        *,
        credit_note_id: uuid.UUID,
        tenant_id: uuid.UUID,
        invoice_id: uuid.UUID,
        amount: Decimal,
        reason: str,
        requested_by: uuid.UUID,
    ) -> CreditNote:
        return cls(
            credit_note_id=credit_note_id,
            tenant_id=tenant_id,
            invoice_id=invoice_id,
            amount=amount,
            reason=reason,
            requested_by=requested_by,
        )

    def approve(self, approved_by: uuid.UUID) -> None:
        if self.is_approved:
            msg = "Credit note has already been approved."
            raise InvariantViolation(msg)

        self._approved_by = approved_by
        self._approved_at = datetime.now(UTC)

        self.record_event(
            RefundApproved(
                credit_note_id=self.id,
                tenant_id=self._tenant_id,
                invoice_id=self._invoice_id,
                amount=self._amount,
                approved_by=approved_by,
            )
        )

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._tenant_id

    @property
    def invoice_id(self) -> uuid.UUID:
        return self._invoice_id

    @property
    def amount(self) -> Decimal:
        return self._amount

    @property
    def reason(self) -> str:
        return self._reason

    @property
    def requested_by(self) -> uuid.UUID:
        return self._requested_by

    @property
    def requested_at(self) -> datetime:
        return self._requested_at

    @property
    def approved_by(self) -> uuid.UUID | None:
        return self._approved_by

    @property
    def approved_at(self) -> datetime | None:
        return self._approved_at

    @property
    def is_approved(self) -> bool:
        return self._approved_at is not None
