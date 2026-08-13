"""Pydantic response models for `api/v1/routers/dashboard.py`.

`uuid`/`datetime`/`Decimal` are real imports, not `TYPE_CHECKING`-guarded —
see `schemas/inventory.py`'s identical note on why Pydantic needs them at
class-definition time.
"""

from __future__ import annotations

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003
from decimal import Decimal  # noqa: TC003

from pydantic import BaseModel


class CylinderTypePriceCardResponse(BaseModel):
    cylinder_type_id: uuid.UUID
    name: str
    weight_kg: Decimal
    customer_type: str
    #: `None` when no price list entry has been configured yet.
    price: Decimal | None


class DashboardActivityEntryResponse(BaseModel):
    id: uuid.UUID
    actor_display_name: str | None
    entity_name: str
    entity_id: str | None
    entity_display_name: str | None
    action: str
    performed_at: datetime


class DashboardSummaryResponse(BaseModel):
    customer_count: int
    driver_count: int
    vehicle_count: int
    vehicles_by_status: dict[str, int]
    warehouse_count: int
    cylinder_type_count: int
    inventory_by_status: dict[str, int]
    price_cards: list[CylinderTypePriceCardResponse]
    #: `before_state`/`after_state` aren't surfaced here — the dashboard's
    #: activity feed is a glance-level summary, not the full audit trail
    #: (that detail is `GET /admin/audit-log`'s job).
    recent_activity: list[DashboardActivityEntryResponse]
