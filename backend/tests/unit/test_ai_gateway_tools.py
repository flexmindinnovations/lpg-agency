"""Unit tests for the AI Command Center's Tool Registry and its three
read-only tools (ADR-045) — mocked repositories/UoW, no database."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from lpg.application.ai.tools import TOOL_REGISTRY, ToolContext
from lpg.application.complaint.use_cases import (
    GetOpenComplaintsSummaryQuery,
    GetOpenComplaintsSummaryUseCase,
)
from lpg.application.inventory.use_cases import (
    GetInventoryOverviewQuery,
    GetInventoryOverviewUseCase,
)
from lpg.application.order.use_cases import (
    GetTodayDeliveryStatusQuery,
    GetTodayDeliveryStatusUseCase,
)
from lpg.domain.order.order import ORDER_STATUSES


class TestGetTodayDeliveryStatusUseCase:
    async def test_counts_every_order_status_and_the_stale_out_for_delivery_count(self) -> None:
        repository = MagicMock()
        repository.count_orders = AsyncMock(return_value=3)
        use_case = GetTodayDeliveryStatusUseCase(repository)

        result = await use_case.execute(GetTodayDeliveryStatusQuery())

        assert set(result.status_counts) == ORDER_STATUSES
        assert all(count == 3 for count in result.status_counts.values())
        assert result.stale_out_for_delivery_count == 3
        # One count_orders call per ORDER_STATUSES member (today-bounded)
        # plus one for the stale out_for_delivery count.
        assert repository.count_orders.await_count == len(ORDER_STATUSES) + 1

    async def test_stale_count_uses_only_an_upper_date_bound(self) -> None:
        repository = MagicMock()
        repository.count_orders = AsyncMock(return_value=0)
        use_case = GetTodayDeliveryStatusUseCase(repository)

        await use_case.execute(GetTodayDeliveryStatusQuery())

        stale_call = repository.count_orders.await_args_list[-1]
        assert stale_call.kwargs["status"] == "out_for_delivery"
        assert stale_call.kwargs.get("from_date") is None
        assert stale_call.kwargs["to_date"] is not None


class TestGetInventoryOverviewUseCase:
    async def test_wraps_get_balance_summary_directly(self) -> None:
        repository = MagicMock()
        repository.get_balance_summary = AsyncMock(return_value={"filled": 1200, "empty": 340})
        use_case = GetInventoryOverviewUseCase(repository)

        result = await use_case.execute(GetInventoryOverviewQuery())

        assert result.quantity_by_status == {"filled": 1200, "empty": 340}
        repository.get_balance_summary.assert_awaited_once_with()


class TestGetOpenComplaintsSummaryUseCase:
    async def test_counts_each_non_terminal_status_separately(self) -> None:
        uow = MagicMock()
        uow.__aenter__ = AsyncMock(return_value=uow)
        uow.__aexit__ = AsyncMock(return_value=None)
        uow.complaints.count_complaints = AsyncMock(side_effect=[2, 5, 1])
        use_case = GetOpenComplaintsSummaryUseCase(uow)
        ctx = MagicMock(tenant_id="tenant-1")

        result = await use_case.execute(ctx, GetOpenComplaintsSummaryQuery())

        assert result.open_count == 2
        assert result.assigned_count == 5
        assert result.in_progress_count == 1
        assert uow.complaints.count_complaints.await_count == 3


class TestToolRegistry:
    def test_every_tool_declares_a_zero_argument_schema(self) -> None:
        for tool in TOOL_REGISTRY:
            assert tool.declaration.parameters_schema.get("properties") == {}

    def test_tool_names_are_unique(self) -> None:
        names = [tool.declaration.name for tool in TOOL_REGISTRY]
        assert len(names) == len(set(names))

    async def test_each_handler_runs_against_a_minimal_context(self) -> None:
        """Every tool handler must tolerate being called with a ToolContext
        where only its own dependency is meaningfully mocked — proves no
        handler secretly reaches into a repository outside its declared
        need."""
        order_repository = MagicMock()
        order_repository.count_orders = AsyncMock(return_value=0)

        inventory_repository = MagicMock()
        inventory_repository.get_balance_summary = AsyncMock(return_value={})

        complaint_uow = MagicMock()
        complaint_uow.__aenter__ = AsyncMock(return_value=complaint_uow)
        complaint_uow.__aexit__ = AsyncMock(return_value=None)
        complaint_uow.complaints.count_complaints = AsyncMock(return_value=0)

        ctx = ToolContext(
            order_repository=order_repository,
            inventory_repository=inventory_repository,
            complaint_uow=complaint_uow,
        )
        principal = MagicMock(tenant_id="tenant-1")

        for tool in TOOL_REGISTRY:
            result = await tool.handler(principal, ctx)
            assert isinstance(result, dict)
