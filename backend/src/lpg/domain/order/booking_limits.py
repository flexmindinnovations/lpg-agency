"""Pure rules behind BR-04 (cylinder holding cap) and BR-19 (credit limit).

Both limits are tenant configuration (BR-31), parameterized by customer type
(D-03, D-11). A config value is either one number for every customer type or
an object keyed by customer type, e.g. `{"domestic": 2, "commercial": 10}`.
A type with no value has no limit — the rules only apply once an agency has
configured them (`docs/engineering/customer-booking.md` step 7).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import uuid
    from collections.abc import Mapping, Sequence


def limit_for_customer_type(config_value: Any, customer_type: str) -> Decimal | None:
    """The configured limit for `customer_type`, or `None` when unlimited.

    Unreadable values (a typo in the admin settings) count as unlimited
    rather than blocking every booking; the settings screen is where they
    get fixed.
    """
    raw = config_value.get(customer_type) if isinstance(config_value, dict) else config_value
    if raw is None or isinstance(raw, bool):
        return None
    try:
        limit = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None
    if not limit.is_finite() or limit < 0:
        return None
    return limit


def projected_cylinder_holding(
    *,
    balances: Mapping[uuid.UUID, int],
    open_order_quantities: Mapping[uuid.UUID, int],
    requested_lines: Sequence[tuple[uuid.UUID, int]],
) -> int:
    """How many cylinders the customer will hold once every open order and
    this booking are delivered.

    A refill is an exchange (BR-02): each delivered cylinder is matched by an
    empty the customer hands back, as long as they hold one of that type. So
    per cylinder type the customer ends up holding the larger of what they
    hold today and what is coming to them; only cylinders beyond today's
    holding add to it.
    """
    requested: dict[uuid.UUID, int] = {}
    for cylinder_type_id, quantity in requested_lines:
        requested[cylinder_type_id] = requested.get(cylinder_type_id, 0) + quantity

    total = 0
    for cylinder_type_id in set(balances) | set(open_order_quantities) | set(requested):
        held = max(balances.get(cylinder_type_id, 0), 0)
        incoming = open_order_quantities.get(cylinder_type_id, 0) + requested.get(
            cylinder_type_id, 0
        )
        total += max(held, incoming)
    return total
