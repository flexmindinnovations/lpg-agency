"""Unit tests for the CashHandover aggregate root.

Covers the shortfall calculation and the `CashShortfallDeclared` event
(R10) — only fired when `actual_amount < expected_amount`.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from lpg.domain.accounting.cash_handover import CashHandover, CashShortfallDeclared
from lpg.domain.common.base import InvariantViolation


def _declare(
    *, expected_amount: Decimal = Decimal("1000.00"), actual_amount: Decimal = Decimal("1000.00")
) -> CashHandover:
    return CashHandover.declare(
        cash_handover_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        driver_id=uuid.uuid4(),
        route_id=uuid.uuid4(),
        expected_amount=expected_amount,
        actual_amount=actual_amount,
        declared_by=uuid.uuid4(),
    )


class TestCashHandoverCreation:
    def test_rejects_negative_expected_amount(self) -> None:
        with pytest.raises(InvariantViolation, match="Expected amount"):
            CashHandover(
                cash_handover_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                driver_id=uuid.uuid4(),
                route_id=uuid.uuid4(),
                expected_amount=Decimal("-1"),
                actual_amount=Decimal("0"),
                declared_by=uuid.uuid4(),
            )

    def test_rejects_negative_actual_amount(self) -> None:
        with pytest.raises(InvariantViolation, match="Actual amount"):
            CashHandover(
                cash_handover_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                driver_id=uuid.uuid4(),
                route_id=uuid.uuid4(),
                expected_amount=Decimal("0"),
                actual_amount=Decimal("-1"),
                declared_by=uuid.uuid4(),
            )


class TestShortfallCalculation:
    def test_exact_match_has_zero_shortfall_and_no_event(self) -> None:
        handover = _declare(expected_amount=Decimal("500"), actual_amount=Decimal("500"))
        assert handover.shortfall == Decimal("0")
        assert handover.events == ()

    def test_handing_over_more_than_expected_has_zero_shortfall_and_no_event(self) -> None:
        handover = _declare(expected_amount=Decimal("500"), actual_amount=Decimal("600"))
        assert handover.shortfall == Decimal("0")
        assert handover.events == ()

    def test_handing_over_less_records_shortfall_and_event(self) -> None:
        handover = _declare(expected_amount=Decimal("500"), actual_amount=Decimal("420"))
        assert handover.shortfall == Decimal("80")

        events = [e for e in handover.events if isinstance(e, CashShortfallDeclared)]
        assert len(events) == 1
        event = events[0]
        assert event.cash_handover_id == handover.id
        assert event.tenant_id == handover.tenant_id
        assert event.driver_id == handover.driver_id
        assert event.route_id == handover.route_id
        assert event.expected_amount == Decimal("500")
        assert event.actual_amount == Decimal("420")
        assert event.shortfall == Decimal("80")
