"""What is still to be paid at the door when a delivery is completed (ADR-069).

One rule, shared by the deliver use case and the driver's settlement preview
so the app and the server never disagree about the balance:

    balance due = payable for what was delivered - money already received online

A delivery is *settled* when the driver collected at least the balance, or
recorded it as credit (the customer takes the cylinders on account).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid
    from collections.abc import Iterable

    from lpg.domain.accounting.online_payment import OnlinePayment
    from lpg.domain.order.order import Order

#: Rounding slack: a driver is never held to a few paise.
SETTLEMENT_TOLERANCE = Decimal("0.50")
CREDIT_METHOD = "credit"


@dataclass(frozen=True, slots=True)
class Settlement:
    #: Price plus GST for the quantities delivered; `None` for an order that
    #: was never priced (nothing to hold the driver to).
    payable: Decimal | None
    #: Online payments already captured for this order.
    paid_online: Decimal
    #: What the driver still has to collect (never negative); `None` when
    #: `payable` is unknown.
    balance_due: Decimal | None

    def is_settled_by(self, *, method: str, amount_collected: Decimal) -> bool:
        if self.balance_due is None or method == CREDIT_METHOD:
            return True
        return amount_collected + SETTLEMENT_TOLERANCE >= self.balance_due


def compute_settlement(
    order: Order,
    delivered: dict[uuid.UUID, int],
    prepayments: Iterable[OnlinePayment],
) -> Settlement:
    paid_online = sum(
        (p.amount for p in prepayments if p.status == "paid"),
        Decimal("0.00"),
    )
    payable = order.payable_for_quantities(delivered)
    balance = None if payable is None else max(payable - paid_online, Decimal("0.00"))
    return Settlement(payable=payable, paid_online=paid_online, balance_due=balance)
