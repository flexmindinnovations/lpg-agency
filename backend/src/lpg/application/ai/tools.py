"""The Tool Registry (ADR-045) — the fixed menu of read-only tools the AI
Command Center's orchestrator (`AskAiAssistantUseCase`, Stage 3) may offer
Gemini for a given request.

Every tool here is zero-argument (parameters_schema's `properties` is always
`{}`) and wraps an existing or newly-thin read use case — no tool talks to a
repository/session directly, and none can mutate anything. Per-tool
`required_permission` is the real prompt-injection defense the user's own
architecture doc describes: the orchestrator filters this registry against
the calling principal's actual grants *before* Gemini ever sees a tool
exists, and even a hallucinated call to an unregistered tool name is
rejected by the orchestrator, never executed (see `AskAiAssistantUseCase`).

`TOOL_REGISTRY` is a static, code-defined tuple — not DB-configurable in
this slice. A future admin-managed registry is a natural extension, not
built here.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.ai.ports import ToolDeclaration

if TYPE_CHECKING:
    from lpg.application.complaint.ports import ComplaintUnitOfWork
    from lpg.application.identity.ports import AuthenticatedPrincipal
    from lpg.application.inventory.ports import InventoryLocationRepository
    from lpg.application.order.ports import OrderRepository


@dataclass(frozen=True, slots=True)
class ToolContext:
    """Request-scoped repositories a tool handler may need — built once per
    `POST /ai/ask` call via the same `Depends()` providers every other
    endpoint already uses. The registry itself never constructs these."""

    order_repository: OrderRepository
    inventory_repository: InventoryLocationRepository
    complaint_uow: ComplaintUnitOfWork


ToolHandler = Callable[["AuthenticatedPrincipal", ToolContext], Awaitable[dict[str, object]]]


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    declaration: ToolDeclaration
    required_permission: str
    handler: ToolHandler


async def _get_today_delivery_status(
    _principal: AuthenticatedPrincipal, ctx: ToolContext
) -> dict[str, object]:
    from lpg.application.order.use_cases import (
        GetTodayDeliveryStatusQuery,
        GetTodayDeliveryStatusUseCase,
    )

    use_case = GetTodayDeliveryStatusUseCase(ctx.order_repository)
    result = await use_case.execute(GetTodayDeliveryStatusQuery())
    return {
        "status_counts": result.status_counts,
        "stale_out_for_delivery_count": result.stale_out_for_delivery_count,
    }


async def _get_inventory_overview(
    _principal: AuthenticatedPrincipal, ctx: ToolContext
) -> dict[str, object]:
    from lpg.application.inventory.use_cases import (
        GetInventoryOverviewQuery,
        GetInventoryOverviewUseCase,
    )

    use_case = GetInventoryOverviewUseCase(ctx.inventory_repository)
    result = await use_case.execute(GetInventoryOverviewQuery())
    return {"quantity_by_status": result.quantity_by_status}


async def _get_open_complaints_summary(
    principal: AuthenticatedPrincipal, ctx: ToolContext
) -> dict[str, object]:
    from lpg.application.complaint.use_cases import (
        GetOpenComplaintsSummaryQuery,
        GetOpenComplaintsSummaryUseCase,
    )

    use_case = GetOpenComplaintsSummaryUseCase(ctx.complaint_uow)
    result = await use_case.execute(principal, GetOpenComplaintsSummaryQuery())
    return {
        "open_count": result.open_count,
        "assigned_count": result.assigned_count,
        "in_progress_count": result.in_progress_count,
    }


TOOL_REGISTRY: tuple[ToolDefinition, ...] = (
    ToolDefinition(
        declaration=ToolDeclaration(
            name="get_today_delivery_status",
            description=(
                "Today's order pipeline: counts of orders by status, plus how "
                "many deliveries are stale (still out for delivery from a day "
                "before today)."
            ),
            parameters_schema={"type": "object", "properties": {}},
        ),
        required_permission="orders:read",
        handler=_get_today_delivery_status,
    ),
    ToolDefinition(
        declaration=ToolDeclaration(
            name="get_inventory_overview",
            description=(
                "Tenant-wide cylinder stock right now, by status "
                "(filled/empty/etc.), across every warehouse and vehicle."
            ),
            parameters_schema={"type": "object", "properties": {}},
        ),
        required_permission="inventory:read",
        handler=_get_inventory_overview,
    ),
    ToolDefinition(
        declaration=ToolDeclaration(
            name="get_open_complaints_summary",
            description=(
                "Count of currently open, assigned, and in-progress customer "
                "complaints."
            ),
            parameters_schema={"type": "object", "properties": {}},
        ),
        required_permission="complaints.manage",
        handler=_get_open_complaints_summary,
    ),
)
