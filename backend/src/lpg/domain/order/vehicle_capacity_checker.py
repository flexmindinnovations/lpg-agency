"""`VehicleCapacityChecker` — BR-09/D-08's partial-fulfilment split.

Pure, no I/O — mirrors `domain/tenant/price_list.py::EffectivePriceResolver`'s
shape exactly. The repository loads the vehicle's current Filled balance per
cylinder type; this decides, for each requested line, how much can actually
be reserved now versus how much is backordered.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


class VehicleCapacityChecker:
    @staticmethod
    def allocate(
        *,
        vehicle_balances: dict[uuid.UUID, int],
        lines: Sequence[tuple[uuid.UUID, int]],
    ) -> dict[uuid.UUID, tuple[int, int]]:
        """Returns `{cylinder_type_id: (reserved, pending)}` for each of
        `lines` (`(cylinder_type_id, quantity_ordered)` pairs). `reserved`
        is capped at the available Filled balance for that cylinder type;
        anything beyond that is `pending` (backordered, D-08). `Order`
        itself never has two lines for the same cylinder type (see its own
        constructor invariant) — the per-type running-balance tracking here
        is defensive, not something a real caller relies on.
        """
        remaining = dict(vehicle_balances)
        allocation: dict[uuid.UUID, tuple[int, int]] = {}
        for cylinder_type_id, quantity_ordered in lines:
            available = remaining.get(cylinder_type_id, 0)
            reserved = min(available, quantity_ordered)
            pending = quantity_ordered - reserved
            remaining[cylinder_type_id] = available - reserved
            allocation[cylinder_type_id] = (reserved, pending)
        return allocation
