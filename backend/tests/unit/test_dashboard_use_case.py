"""Unit tests for `GetDashboardSummaryUseCase`.

Uses mocked repositories — no database required.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from lpg.application.audit.ports import AuditLogPage
from lpg.application.dashboard.get_dashboard_summary import (
    GetDashboardSummaryQuery,
    GetDashboardSummaryUseCase,
)
from lpg.domain.tenant.cylinder_type import CylinderType
from lpg.domain.tenant.price_list import PriceListEntry


def _make_use_case(
    *,
    customer_repo: MagicMock,
    driver_repo: MagicMock,
    vehicle_repo: MagicMock,
    warehouse_repo: MagicMock,
    cylinder_type_repo: MagicMock,
    inventory_location_repo: MagicMock,
    price_list_repo: MagicMock,
    audit_log_repo: MagicMock,
) -> GetDashboardSummaryUseCase:
    return GetDashboardSummaryUseCase(
        customer_repository=customer_repo,
        driver_repository=driver_repo,
        vehicle_repository=vehicle_repo,
        warehouse_repository=warehouse_repo,
        cylinder_type_repository=cylinder_type_repo,
        inventory_location_repository=inventory_location_repo,
        price_list_repository=price_list_repo,
        audit_log_repository=audit_log_repo,
    )


def _mock_repos() -> dict[str, MagicMock]:
    customer_repo = MagicMock()
    customer_repo.count_customers = AsyncMock(return_value=3)

    driver_repo = MagicMock()
    driver_repo.count_drivers = AsyncMock(return_value=2)

    vehicle_repo = MagicMock()
    vehicle_repo.count_vehicles = AsyncMock(return_value=5)
    vehicle_repo.count_by_status = AsyncMock(return_value={"active": 4, "maintenance": 1})

    warehouse_repo = MagicMock()
    warehouse_repo.list_for_tenant = AsyncMock(return_value=[])

    cylinder_type_repo = MagicMock()
    cylinder_type_repo.list_for_tenant = AsyncMock(return_value=[])

    inventory_location_repo = MagicMock()
    inventory_location_repo.get_balance_summary = AsyncMock(
        return_value={"filled": 100, "empty": 20}
    )

    price_list_repo = MagicMock()
    price_list_repo.list_for_tenant_and_cylinder_type = AsyncMock(return_value=[])

    audit_log_repo = MagicMock()
    audit_log_repo.get_page = AsyncMock(return_value=AuditLogPage(items=[], next_cursor=None))

    return {
        "customer_repo": customer_repo,
        "driver_repo": driver_repo,
        "vehicle_repo": vehicle_repo,
        "warehouse_repo": warehouse_repo,
        "cylinder_type_repo": cylinder_type_repo,
        "inventory_location_repo": inventory_location_repo,
        "price_list_repo": price_list_repo,
        "audit_log_repo": audit_log_repo,
    }


async def test_dashboard_summary_composes_counts_from_every_context() -> None:
    repos = _mock_repos()
    use_case = _make_use_case(**repos)
    tenant_id = uuid.uuid4()

    summary = await use_case.execute(GetDashboardSummaryQuery(tenant_id=tenant_id))

    assert summary.customer_count == 3
    assert summary.driver_count == 2
    assert summary.vehicle_count == 5
    assert summary.vehicles_by_status == {"active": 4, "maintenance": 1}
    assert summary.warehouse_count == 0
    assert summary.cylinder_type_count == 0
    assert summary.inventory_by_status == {"filled": 100, "empty": 20}
    assert summary.price_cards == []
    assert summary.recent_activity.items == []
    repos["audit_log_repo"].get_page.assert_called_once_with(tenant_id, limit=8)


async def test_dashboard_summary_skips_inactive_cylinder_types_for_price_cards() -> None:
    repos = _mock_repos()
    tenant_id = uuid.uuid4()
    active_type = CylinderType(
        cylinder_type_id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="14.2kg",
        weight_kg=Decimal("14.2"),
        is_active=True,
    )
    inactive_type = CylinderType(
        cylinder_type_id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="19kg (retired)",
        weight_kg=Decimal("19"),
        is_active=False,
    )
    repos["cylinder_type_repo"].list_for_tenant = AsyncMock(
        return_value=[active_type, inactive_type]
    )
    use_case = _make_use_case(**repos)

    summary = await use_case.execute(GetDashboardSummaryQuery(tenant_id=tenant_id))

    assert summary.cylinder_type_count == 2
    assert len(summary.price_cards) == 1
    assert summary.price_cards[0].cylinder_type_id == active_type.id
    assert summary.price_cards[0].price is None
    repos["price_list_repo"].list_for_tenant_and_cylinder_type.assert_called_once_with(
        tenant_id, active_type.id, "domestic"
    )


async def test_dashboard_summary_resolves_effective_price_for_price_cards() -> None:
    repos = _mock_repos()
    tenant_id = uuid.uuid4()
    cylinder_type = CylinderType(
        cylinder_type_id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="14.2kg",
        weight_kg=Decimal("14.2"),
    )
    repos["cylinder_type_repo"].list_for_tenant = AsyncMock(return_value=[cylinder_type])
    entry = PriceListEntry(
        entry_id=uuid.uuid4(),
        tenant_id=tenant_id,
        cylinder_type_id=cylinder_type.id,
        customer_type="domestic",
        price=Decimal("950.00"),
        effective_from=datetime(2026, 1, 1, tzinfo=UTC),
    )
    repos["price_list_repo"].list_for_tenant_and_cylinder_type = AsyncMock(return_value=[entry])
    use_case = _make_use_case(**repos)

    summary = await use_case.execute(GetDashboardSummaryQuery(tenant_id=tenant_id))

    assert len(summary.price_cards) == 1
    assert summary.price_cards[0].price == Decimal("950.00")
    assert summary.price_cards[0].name == "14.2kg"
