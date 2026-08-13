"""FastAPI router for the dashboard summary read model.

Exposes a single consolidated `GET /dashboard/summary` for the frontend's
Agency Overview page, gated by `reports:read`
(`backend/migrations/versions/b3f7c1d9e4a2_grant_reports_read_permission.py`).
Replaces the frontend's previous client-side N+1 aggregation across every
warehouse/vehicle's inventory balance with one server-side query.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from lpg.api.v1.dependencies.dashboard import get_dashboard_summary_use_case
from lpg.api.v1.dependencies.identity import require_permission
from lpg.api.v1.schemas.dashboard import (
    CylinderTypePriceCardResponse,
    DashboardActivityEntryResponse,
    DashboardSummaryResponse,
)
from lpg.application.dashboard.get_dashboard_summary import (
    GetDashboardSummaryQuery,
    GetDashboardSummaryUseCase,
)
from lpg.application.identity.ports import AuthenticatedPrincipal

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/summary",
    response_model=DashboardSummaryResponse,
    summary="Consolidated platform-wide summary for the dashboard",
)
async def get_dashboard_summary(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("reports:read"))],
    use_case: Annotated[GetDashboardSummaryUseCase, Depends(get_dashboard_summary_use_case)],
) -> DashboardSummaryResponse:
    summary = await use_case.execute(GetDashboardSummaryQuery(tenant_id=principal.tenant_id))
    return DashboardSummaryResponse(
        customer_count=summary.customer_count,
        driver_count=summary.driver_count,
        vehicle_count=summary.vehicle_count,
        vehicles_by_status=summary.vehicles_by_status,
        warehouse_count=summary.warehouse_count,
        cylinder_type_count=summary.cylinder_type_count,
        inventory_by_status=summary.inventory_by_status,
        price_cards=[
            CylinderTypePriceCardResponse(
                cylinder_type_id=card.cylinder_type_id,
                name=card.name,
                weight_kg=card.weight_kg,
                customer_type=card.customer_type,
                price=card.price,
            )
            for card in summary.price_cards
        ],
        recent_activity=[
            DashboardActivityEntryResponse(
                id=entry.id,
                actor_display_name=entry.actor_display_name,
                entity_name=entry.entity_name,
                entity_id=entry.entity_id,
                entity_display_name=entry.entity_display_name,
                action=entry.action,
                performed_at=entry.performed_at,
            )
            for entry in summary.recent_activity.items
        ],
    )
