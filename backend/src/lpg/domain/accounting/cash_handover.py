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
    ) -> CashHandover:
        handover = cls(
            cash_handover_id=cash_handover_id,
            tenant_id=tenant_id,
            driver_id=driver_id,
            route_id=route_id,
            expected_amount=expected_amount,
            actual_amount=actual_amount,
            declared_by=declared_by,
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
