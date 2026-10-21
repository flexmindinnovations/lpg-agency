"""DO-10: the real BR-04 (cylinder holding cap) and BR-19 (credit limit)
checks, driven by tenant configuration."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from lpg.application.common.errors import CreditLimitExceededError, CylinderCapExceededError
from lpg.application.order.booking_policies import (
    CREDIT_LIMIT_CONFIG_KEY,
    CYLINDER_HOLDING_CAP_CONFIG_KEY,
    LedgerCylinderCapPolicy,
    OutstandingBalanceCreditLimitEvaluator,
)
from lpg.domain.cylinder_ledger.cylinder_ledger import CylinderLedger
from lpg.domain.order.booking_limits import limit_for_customer_type, projected_cylinder_holding
from lpg.domain.tenant.tenant_configuration import TenantConfiguration

TENANT = uuid.uuid4()
CUSTOMER = uuid.uuid4()
DOMESTIC_14KG = uuid.uuid4()
DOMESTIC_5KG = uuid.uuid4()


def _configuration(key: str, value: Any) -> MagicMock:
    repo = MagicMock()
    entries = (
        []
        if value is None
        else [
            TenantConfiguration(
                uuid.uuid4(), TENANT, key, value, datetime.now(UTC) - timedelta(days=1)
            )
        ]
    )
    repo.list_for_tenant_and_key = AsyncMock(return_value=entries)
    return repo


class TestLimitForCustomerType:
    @pytest.mark.parametrize(
        ("value", "customer_type", "expected"),
        [
            (2, "domestic", Decimal(2)),
            ({"domestic": 2, "commercial": 10}, "commercial", Decimal(10)),
            ({"domestic": 2}, "commercial", None),
            (None, "domestic", None),
            ("lots", "domestic", None),
            (-1, "domestic", None),
            (True, "domestic", None),
        ],
    )
    def test_reads_one_number_or_a_per_type_map(
        self, value: Any, customer_type: str, expected: Decimal | None
    ) -> None:
        assert limit_for_customer_type(value, customer_type) == expected


class TestProjectedHolding:
    def test_a_refill_exchanges_an_empty_and_adds_nothing(self) -> None:
        assert (
            projected_cylinder_holding(
                balances={DOMESTIC_14KG: 2},
                open_order_quantities={},
                requested_lines=[(DOMESTIC_14KG, 1)],
            )
            == 2
        )

    def test_open_orders_and_new_types_add_to_the_holding(self) -> None:
        assert (
            projected_cylinder_holding(
                balances={DOMESTIC_14KG: 1},
                open_order_quantities={DOMESTIC_14KG: 1},
                requested_lines=[(DOMESTIC_14KG, 1), (DOMESTIC_5KG, 1)],
            )
            == 3
        )


class TestCylinderCapPolicy:
    def _policy(self, cap: Any, held: int, open_quantity: int) -> LedgerCylinderCapPolicy:
        ledger_repo = MagicMock()
        ledger_repo.get_by_customer_id = AsyncMock(
            return_value=CylinderLedger(
                cylinder_ledger_id=uuid.uuid4(),
                tenant_id=TENANT,
                customer_id=CUSTOMER,
                balances={DOMESTIC_14KG: held},
            )
        )
        open_orders = MagicMock()
        open_orders.open_quantities = AsyncMock(return_value={DOMESTIC_14KG: open_quantity})
        return LedgerCylinderCapPolicy(
            _configuration(CYLINDER_HOLDING_CAP_CONFIG_KEY, cap), ledger_repo, open_orders
        )

    async def test_no_configured_cap_allows_any_booking(self) -> None:
        await self._policy(None, held=0, open_quantity=0).evaluate(
            tenant_id=TENANT,
            customer_id=CUSTOMER,
            customer_type="domestic",
            requested_lines=[(DOMESTIC_14KG, 50)],
        )

    async def test_within_the_cap_is_allowed(self) -> None:
        await self._policy({"domestic": 2}, held=1, open_quantity=0).evaluate(
            tenant_id=TENANT,
            customer_id=CUSTOMER,
            customer_type="domestic",
            requested_lines=[(DOMESTIC_14KG, 2)],
        )

    async def test_over_the_cap_is_refused_with_a_clear_message(self) -> None:
        with pytest.raises(CylinderCapExceededError, match="at most 2") as raised:
            await self._policy({"domestic": 2}, held=1, open_quantity=2).evaluate(
                tenant_id=TENANT,
                customer_id=CUSTOMER,
                customer_type="domestic",
                requested_lines=[(DOMESTIC_14KG, 1)],
            )
        assert "holding 3 cylinders" in str(raised.value)

    async def test_the_order_being_confirmed_is_left_out_of_open_orders(self) -> None:
        policy = self._policy(2, held=0, open_quantity=0)
        order_id = uuid.uuid4()
        await policy.evaluate(
            tenant_id=TENANT,
            customer_id=CUSTOMER,
            customer_type="domestic",
            requested_lines=[(DOMESTIC_14KG, 2)],
            exclude_order_id=order_id,
        )
        policy._open_orders.open_quantities.assert_awaited_once_with(  # type: ignore[attr-defined]
            CUSTOMER, exclude_order_id=order_id
        )


class TestCreditLimitEvaluator:
    def _evaluator(self, limit: Any, outstanding: str) -> OutstandingBalanceCreditLimitEvaluator:
        invoices = MagicMock()
        invoices.get_outstanding_balance = AsyncMock(return_value=Decimal(outstanding))
        return OutstandingBalanceCreditLimitEvaluator(
            _configuration(CREDIT_LIMIT_CONFIG_KEY, limit), invoices
        )

    async def test_no_configured_limit_allows_any_order(self) -> None:
        await self._evaluator(None, "999999").evaluate(
            tenant_id=TENANT,
            customer_id=CUSTOMER,
            customer_type="domestic",
            order_total=Decimal("1000"),
        )

    async def test_up_to_the_limit_is_allowed(self) -> None:
        await self._evaluator({"commercial": 5000}, "4000").evaluate(
            tenant_id=TENANT,
            customer_id=CUSTOMER,
            customer_type="commercial",
            order_total=Decimal("1000"),
        )

    async def test_over_the_limit_is_refused(self) -> None:
        with pytest.raises(CreditLimitExceededError, match=r"credit limit of ₹5,000\.00"):
            await self._evaluator(5000, "4500").evaluate(
                tenant_id=TENANT,
                customer_id=CUSTOMER,
                customer_type="domestic",
                order_total=Decimal("1000"),
            )
