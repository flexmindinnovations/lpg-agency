"""Unit tests for `CancellationFeeCalculator.calculate()` (D-19)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from lpg.domain.common.base import InvariantViolation
from lpg.domain.order.cancellation_fee import CancellationFeeCalculator


def test_no_configured_policy_means_no_fee() -> None:
    fee = CancellationFeeCalculator.calculate(config_value=None, order_total=Decimal("1000"))
    assert fee == Decimal("0")


def test_flat_fee_below_order_total() -> None:
    fee = CancellationFeeCalculator.calculate(
        config_value={"policy_type": "flat", "amount": "150.00"}, order_total=Decimal("1000")
    )
    assert fee == Decimal("150.00")


def test_flat_fee_capped_at_order_total() -> None:
    fee = CancellationFeeCalculator.calculate(
        config_value={"policy_type": "flat", "amount": "5000"}, order_total=Decimal("300")
    )
    assert fee == Decimal("300")


def test_percentage_fee_rounds_to_two_decimal_places() -> None:
    fee = CancellationFeeCalculator.calculate(
        config_value={"policy_type": "percentage", "amount": "10"}, order_total=Decimal("999.99")
    )
    assert fee == Decimal("100.00")


def test_percentage_fee_capped_at_order_total() -> None:
    fee = CancellationFeeCalculator.calculate(
        config_value={"policy_type": "percentage", "amount": "150"}, order_total=Decimal("200")
    )
    assert fee == Decimal("200")


def test_unknown_policy_type_raises() -> None:
    with pytest.raises(InvariantViolation, match="Unknown cancellation fee policy type"):
        CancellationFeeCalculator.calculate(
            config_value={"policy_type": "lottery", "amount": "1"}, order_total=Decimal("100")
        )
