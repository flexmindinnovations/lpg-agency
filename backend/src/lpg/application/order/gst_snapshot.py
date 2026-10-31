"""The GST an order is quoted with, fixed when it is priced.

An order stores each line's unit price when it is confirmed. This adds the
GST rate quoted with it and whether the tenant's prices include GST, so the
amount the customer pays (the price plus GST when prices are exclusive) does
not move if a rate changes afterwards (planning/features/55).

A cylinder type with no GST rate does not stop an order being confirmed; the
order is simply left without a snapshot and the invoice, which does insist on
a rate, reports it as before (DA-06).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from lpg.application.accounting.gst import (
    GstNotConfiguredError,
    resolve_gst_classes,
    resolve_prices_include_gst,
)
from lpg.config.logging import get_logger

if TYPE_CHECKING:
    import uuid
    from collections.abc import Iterable
    from decimal import Decimal

    from lpg.application.tenant.ports import (
        CylinderTypeRepository,
        TenantConfigurationRepository,
    )

_logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class GstSnapshot:
    """The GST rate of each cylinder type on an order, and whether the unit
    prices already include it."""

    rates: dict[uuid.UUID, Decimal]
    prices_include_gst: bool


class OrderGstSnapshotter:
    def __init__(
        self,
        cylinder_type_repository: CylinderTypeRepository,
        tenant_config_repository: TenantConfigurationRepository,
    ) -> None:
        self._cylinder_types = cylinder_type_repository
        self._config = tenant_config_repository

    async def snapshot(
        self, *, tenant_id: uuid.UUID, cylinder_type_ids: Iterable[uuid.UUID]
    ) -> GstSnapshot | None:
        """The snapshot for these cylinder types, or `None` when any of them
        has no GST rate set up."""
        at = datetime.now(UTC)
        try:
            classes = await resolve_gst_classes(
                cylinder_type_repository=self._cylinder_types,
                tenant_config_repository=self._config,
                tenant_id=tenant_id,
                cylinder_type_ids=cylinder_type_ids,
                at=at,
            )
        except GstNotConfiguredError:
            _logger.warning("order_gst_not_snapshotted", tenant_id=str(tenant_id))
            return None
        inclusive = await resolve_prices_include_gst(self._config, tenant_id, at)
        return GstSnapshot(
            rates={cid: gst.rate_percent for cid, gst in classes.items()},
            prices_include_gst=inclusive,
        )
