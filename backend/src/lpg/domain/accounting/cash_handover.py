"""`CashHandover` aggregate root.

A driver's declared cash handover for one completed route (BR-32).
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
class CashShortfallDeclared(DomainEvent):
    """Fired only when `actual_amount < expected_amount` (BR-32) — a
    handover that matches or exceeds what was expected records no event;
    there is nothing for a manager-alert consumer to act on.
    """

    cash_handover_id: uuid.UUID
    tenant_id: uuid.UUID
    driver_id: uuid.UUID
    route_id: uuid.UUID
    expected_amount: Decimal
    actual_amount: Decimal
    shortfall: Decimal


# ---------------------------------------------------------------------------
# Aggregate Root
# ---------------------------------------------------------------------------


class CashHandover(AggregateRoot):
    """`expected_amount` is supplied by the use case, computed from real
    `orders.proof_of_delivery` data — this aggregate has no visibility into
    delivery records (Clean Architecture layering).
    """

    __slots__ = (
        "_actual_amount",
        "_declared_at",
        "_declared_by",
        "_driver_id",
        "_expected_amount",
        "_handover_number",
        "_route_id",
        "_tenant_id",
    )

    def __init__(
        self,
        *,
        cash_handover_id: uuid.UUID,
        tenant_id: uuid.UUID,
        driver_id: uuid.UUID,
        route_id: uuid.UUID,
        expected_amount: Decimal,
        actual_amount: Decimal,
        declared_by: uuid.UUID,
        handover_number: str | None = None,
        declared_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(cash_handover_id, version=version)
        if expected_amount < 0:
            msg = f"Expected amount cannot be negative: {expected_amount}."
            raise InvariantViolation(msg)
        if actual_amount < 0:
            msg = f"Actual amount cannot be negative: {actual_amount}."
            raise InvariantViolation(msg)

        self._tenant_id = tenant_id
        self._driver_id = driver_id
        self._handover_number = handover_number
        self._route_id = route_id
        self._expected_amount = expected_amount
        self._actual_amount = actual_amount
        self._declared_by = declared_by
        self._declared_at = declared_at or datetime.now(UTC)

    @classmethod
    def declare(
        cls,
        *,
        cash_handover_id: uuid.UUID,
        tenant_id: uuid.UUID,
        driver_id: uuid.UUID,
        route_id: uuid.UUID,
        expected_amount: Decimal,
        actual_amount: Decimal,
        declared_by: uuid.UUID,
        handover_number: str,
    ) -> CashHandover:
        handover = cls(
            cash_handover_id=cash_handover_id,
            tenant_id=tenant_id,
            driver_id=driver_id,
            route_id=route_id,
            expected_amount=expected_amount,
            actual_amount=actual_amount,
            declared_by=declared_by,
            handover_number=handover_number,
        )
        if handover.shortfall > 0:
            handover.record_event(
                CashShortfallDeclared(
                    cash_handover_id=handover.id,
                    tenant_id=tenant_id,
                    driver_id=driver_id,
                    route_id=route_id,
                    expected_amount=expected_amount,
                    actual_amount=actual_amount,
                    shortfall=handover.shortfall,
                )
            )
        return handover

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._tenant_id

    @property
    def driver_id(self) -> uuid.UUID:
        return self._driver_id

    @property
    def route_id(self) -> uuid.UUID:
        return self._route_id

    @property
    def handover_number(self) -> str | None:
        return self._handover_number

    @property
    def expected_amount(self) -> Decimal:
        return self._expected_amount

    @property
    def actual_amount(self) -> Decimal:
        return self._actual_amount

    @property
    def declared_by(self) -> uuid.UUID:
        return self._declared_by

    @property
    def declared_at(self) -> datetime:
        return self._declared_at

    @property
    def shortfall(self) -> Decimal:
        difference = self._expected_amount - self._actual_amount
        return difference if difference > 0 else Decimal("0")


# ---------------------------------------------------------------------------
# Office review (DA-33)
# ---------------------------------------------------------------------------

#: `accepted` — the cash was counted and matches what the register shows
#: (any shortfall is acknowledged). `disputed` — the count does not match
#: the declaration, or a shortfall needs following up with the driver.
CASH_HANDOVER_REVIEW_OUTCOMES: frozenset[str] = frozenset({"accepted", "disputed"})


@dataclass(frozen=True, slots=True)
class CashHandoverReview:
    """An accountant's or manager's verdict on a declared handover.

    Append-only, one per handover — like the handover itself, a review is a
    record of what someone attested at a point in time, never edited.
    """

    id: uuid.UUID
    tenant_id: uuid.UUID
    cash_handover_id: uuid.UUID
    outcome: str
    note: str | None
    reviewed_by: uuid.UUID
    reviewed_at: datetime

    @classmethod
    def record(
        cls,
        *,
        review_id: uuid.UUID,
        handover: CashHandover,
        outcome: str,
        note: str | None,
        reviewed_by: uuid.UUID,
        reviewed_at: datetime | None = None,
    ) -> CashHandoverReview:
        if outcome not in CASH_HANDOVER_REVIEW_OUTCOMES:
            msg = f"'{outcome}' is not a valid review outcome."
            raise InvariantViolation(msg, outcome=outcome)
        clean_note = (note or "").strip() or None
        if outcome == "disputed" and clean_note is None:
            msg = "Say what is wrong with this handover so the driver can be asked about it."
            raise InvariantViolation(msg, field="note")
        if handover.shortfall > 0 and outcome == "accepted" and clean_note is None:
            msg = "This handover is short. Add a note on how the shortfall was settled."
            raise InvariantViolation(msg, field="note")
        # Segregation of duties: whoever declared the cash cannot also
        # sign it off.
        if reviewed_by == handover.declared_by:
            msg = "The person who declared this handover cannot also verify it."
            raise InvariantViolation(msg, cash_handover_id=str(handover.id))
        return cls(
            id=review_id,
            tenant_id=handover.tenant_id,
            cash_handover_id=handover.id,
            outcome=outcome,
            note=clean_note,
            reviewed_by=reviewed_by,
            reviewed_at=reviewed_at or datetime.now(UTC),
        )
