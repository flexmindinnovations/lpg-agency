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
        handover_number="CSH000001",
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


class TestCountedHandover:
    @staticmethod
    def _counted(
        *,
        expected: str,
        actual: str,
        denominations: dict[int, int] | None,
        reason: str | None = None,
    ) -> CashHandover:
        return CashHandover.declare(
            cash_handover_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            driver_id=uuid.uuid4(),
            route_id=uuid.uuid4(),
            expected_amount=Decimal(expected),
            actual_amount=Decimal(actual),
            declared_by=uuid.uuid4(),
            handover_number="CSH000002",
            denominations=denominations,
            variance_reason=reason,
        )

    def test_notes_must_add_up(self) -> None:
        with pytest.raises(InvariantViolation, match="add up to 1100"):
            self._counted(expected="1200", actual="1200", denominations={500: 2, 100: 1})

    def test_unknown_note_value_is_rejected(self) -> None:
        with pytest.raises(InvariantViolation, match="not a note or coin"):
            self._counted(expected="30", actual="30", denominations={30: 1})

    def test_matching_count_needs_no_reason_and_drops_zero_counts(self) -> None:
        handover = self._counted(
            expected="1100", actual="1100", denominations={500: 2, 100: 1, 50: 0}
        )
        assert handover.denominations == {500: 2, 100: 1}
        assert handover.variance_reason is None

    def test_shortfall_needs_a_reason(self) -> None:
        with pytest.raises(InvariantViolation, match="Say why"):
            self._counted(expected="1200", actual="1100", denominations={500: 2, 100: 1})

    def test_excess_needs_a_reason_and_is_reported(self) -> None:
        handover = self._counted(
            expected="1000",
            actual="1100",
            denominations={500: 2, 100: 1},
            reason="  Customer paid extra  ",
        )
        assert handover.excess == Decimal("100")
        assert handover.shortfall == Decimal("0")
        assert handover.variance_reason == "Customer paid extra"

    def test_amount_only_declaration_still_works(self) -> None:
        handover = self._counted(expected="1200", actual="1100", denominations=None)
        assert handover.denominations is None
        assert handover.shortfall == Decimal("100")
