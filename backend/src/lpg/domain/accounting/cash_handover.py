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


#: Note and coin values a count may use, in rupees. 2000 stays because notes
#: remain in circulation after withdrawal.
CASH_DENOMINATIONS: tuple[int, ...] = (2000, 500, 200, 100, 50, 20, 10, 5, 2, 1)


def validate_denominations(denominations: dict[int, int], total: Decimal) -> dict[int, int]:
    """Counts per note/coin, dropping zero counts. Must add up to `total`."""
    clean: dict[int, int] = {}
    for value, count in denominations.items():
        if value not in CASH_DENOMINATIONS:
            msg = f"{value} is not a note or coin value."
            raise InvariantViolation(msg, field="denominations")
        if count < 0:
            msg = "A count cannot be negative."
            raise InvariantViolation(msg, field="denominations")
        if count:
            clean[value] = count
    counted = sum(value * count for value, count in clean.items())
    if Decimal(counted) != total:
        msg = f"The counted notes add up to {counted}, not the declared {total}."
        raise InvariantViolation(msg, field="denominations")
    return clean


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
        "_denominations",
        "_driver_id",
        "_expected_amount",
        "_handover_number",
        "_route_id",
        "_tenant_id",
        "_upi_expected",
        "_variance_reason",
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
        denominations: dict[int, int] | None = None,
        variance_reason: str | None = None,
        upi_expected: Decimal | None = None,
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
        self._denominations = denominations
        self._variance_reason = variance_reason
        self._upi_expected = upi_expected

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
        denominations: dict[int, int] | None = None,
        variance_reason: str | None = None,
        upi_expected: Decimal | None = None,
    ) -> CashHandover:
        clean_denominations: dict[int, int] | None = None
        reason = (variance_reason or "").strip() or None
        if denominations is not None:
            # A counted handover (ADR-066): the notes must add up, and any
            # difference from the deliveries needs a reason. Clients that
            # send only an amount (older apps) keep the earlier behaviour.
            clean_denominations = validate_denominations(denominations, actual_amount)
            if actual_amount != expected_amount and reason is None:
                msg = "Say why the cash differs from what the deliveries account for."
                raise InvariantViolation(msg, field="variance_reason")
        handover = cls(
            cash_handover_id=cash_handover_id,
            tenant_id=tenant_id,
            driver_id=driver_id,
            route_id=route_id,
            expected_amount=expected_amount,
            actual_amount=actual_amount,
            declared_by=declared_by,
            handover_number=handover_number,
            denominations=clean_denominations,
            variance_reason=reason,
            upi_expected=upi_expected,
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
    def denominations(self) -> dict[int, int] | None:
        return self._denominations

    @property
    def variance_reason(self) -> str | None:
        return self._variance_reason

    @property
    def upi_expected(self) -> Decimal | None:
        return self._upi_expected

    @property
    def excess(self) -> Decimal:
        difference = self._actual_amount - self._expected_amount
        return difference if difference > 0 else Decimal("0")

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
