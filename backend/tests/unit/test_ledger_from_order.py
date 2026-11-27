"""The cylinder ledger projection of a delivered order."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

from lpg.application.cylinder_ledger.use_cases import AppendLedgerTransactionsFromOrderUseCase
from lpg.domain.cylinder_ledger.cylinder_ledger import CylinderLedger
from lpg.domain.order.order import CollectedEmpty, OrderLine


async def test_empties_of_other_sizes_come_off_what_the_customer_holds() -> None:
    ordered, other = uuid.uuid4(), uuid.uuid4()
    ledger = CylinderLedger(
        cylinder_ledger_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        balances={ordered: 10, other: 3},
    )
    order = MagicMock()
    order.id = uuid.uuid4()
    order.status = "delivered"
    order.lines = [
        OrderLine(uuid.uuid4(), ordered, 5, quantity_delivered=5, quantity_collected_empty=10)
    ]
    order.other_empties = (CollectedEmpty(cylinder_type_id=other, quantity=2),)
    orders = MagicMock()
    orders.get_by_id = AsyncMock(return_value=order)
    ledgers = MagicMock()
    ledgers.get_by_customer_id = AsyncMock(return_value=ledger)
    ledgers.add = AsyncMock()

    await AppendLedgerTransactionsFromOrderUseCase(ledgers, orders).execute(
        tenant_id=ledger.tenant_id, order_id=order.id, performed_by=uuid.uuid4()
    )

    # 10 held, 5 delivered and 10 taken back; 3 held of the other size, 2 back.
    assert ledger.balances == {ordered: 5, other: 1}
    ledgers.add.assert_awaited_once_with(ledger)
