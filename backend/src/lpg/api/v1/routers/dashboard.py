"""FastAPI router for the dashboard summary read model.

Exposes a single consolidated `GET /dashboard/summary` for the frontend's
Agency Overview page, gated by `reports:read`
(`backend/migrations/versions/b3f7c1d9e4a2_grant_reports_read_permission.py`).
Replaces the frontend's previous client-side N+1 aggregation across every
warehouse/vehicle's inventory balance with one server-side query.
"""

from __future__ import annotations

from datetime import datetime, time
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends

from lpg.api.v1.dependencies.dashboard import (
    get_dashboard_summary_use_case,
    get_operations_snapshot_use_case,
)
from lpg.api.v1.dependencies.identity import require_permission
from lpg.api.v1.schemas.dashboard import (
    CashSnapshotResponse,
    CylinderTypePriceCardResponse,
    DashboardActivityEntryResponse,
    DashboardSummaryResponse,
    InvoiceSnapshotResponse,
    OperationsSnapshotResponse,
    OrderPipelineResponse,
)
from lpg.application.dashboard.get_dashboard_summary import (
    GetDashboardSummaryQuery,
    GetDashboardSummaryUseCase,
)
from lpg.application.dashboard.get_operations_snapshot import (
    GetOperationsSnapshotQuery,
    GetOperationsSnapshotUseCase,
)
from lpg.application.identity.ports import AuthenticatedPrincipal

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

#: The agency's business day — Indian agencies only (D-06).
_IST = ZoneInfo("Asia/Kolkata")


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


@router.get(
    "/operations",
    response_model=OperationsSnapshotResponse,
    summary="Today's operations KPIs for the Home page",
)
async def get_operations_snapshot(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("reports:read"))],
    use_case: Annotated[GetOperationsSnapshotUseCase, Depends(get_operations_snapshot_use_case)],
) -> OperationsSnapshotResponse:
    """Bookings today, the open order pipeline, deliveries done and failed
    today, cancellations awaiting approval, open complaints, low stock,
    unpaid and overdue invoices, and cash still with drivers (DO-28).
    """
    permissions = principal.permission_codes
    snapshot = await use_case.execute(
        GetOperationsSnapshotQuery(
            tenant_id=principal.tenant_id,
            day_start=datetime.combine(datetime.now(_IST).date(), time.min, tzinfo=_IST),
            include_invoices="invoices:read" in permissions,
            include_cash=bool({"cash_handovers:review", "cash_handovers:declare"} & permissions),
        )
    )
    orders = snapshot.orders
    return OperationsSnapshotResponse(
        orders=OrderPipelineResponse(
            bookings_today=orders.bookings_today,
            open_by_status=orders.open_by_status,
            delivered_today=orders.delivered_today,
            failed_today=orders.failed_today,
            pending_cancellations=orders.pending_cancellations,
        ),
        open_complaints=snapshot.open_complaints,
        low_stock_count=snapshot.low_stock_count,
        invoices=(
            InvoiceSnapshotResponse(
                outstanding_count=snapshot.invoices.outstanding_count,
                outstanding_amount=snapshot.invoices.outstanding_amount,
                overdue_count=snapshot.invoices.overdue_count,
                overdue_amount=snapshot.invoices.overdue_amount,
                on_hold_count=snapshot.invoices.on_hold_count,
            )
            if snapshot.invoices is not None
            else None
        ),
        cash=(
            CashSnapshotResponse(
                awaiting_handover=snapshot.cash.awaiting_handover,
                handovers_awaiting_review=snapshot.cash.handovers_awaiting_review,
            )
            if snapshot.cash is not None
            else None
        ),
        payment_terms_days=snapshot.payment_terms_days,
    )
