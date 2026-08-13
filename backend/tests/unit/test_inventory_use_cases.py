"""Unit tests for inventory use cases.

Uses mocked repositories and UoW — no database required.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from lpg.application.inventory.ports import (
    GoodsReceiptNoteEntry,
    InventoryTransactionPage,
    ReconciliationRecordEntry,
)
from lpg.application.inventory.use_cases import (
    AdjustInventoryCommand,
    AdjustInventoryUseCase,
    ApproveReconciliationCommand,
    ApproveReconciliationUseCase,
    ChangeCylinderStatusCommand,
    ChangeCylinderStatusUseCase,
    CreateReconciliationRecordCommand,
    CreateReconciliationRecordUseCase,
    GetInventoryBalanceQuery,
    GetInventoryBalanceUseCase,
    GetOrCreateInventoryLocationUseCase,
    ListInventoryTransactionsQuery,
    ListInventoryTransactionsUseCase,
    LoadTransferCommand,
    LoadTransferLine,
    LoadTransferUseCase,
    RecordGoodsReceiptCommand,
    RecordGoodsReceiptUseCase,
)
from lpg.domain.inventory.inventory_location import (
    InsufficientStockError,
    InvalidStatusTransitionError,
    InventoryLocation,
)


@pytest.fixture
def mock_uow() -> MagicMock:
    uow = MagicMock()
    uow.commit = AsyncMock()
    uow.register_aggregate = MagicMock()
    return uow


@pytest.fixture
def mock_location_repo() -> MagicMock:
    repo = MagicMock()
    repo.next_id = MagicMock(side_effect=lambda: uuid.uuid4())
    repo.save = AsyncMock()
    repo.get_by_location_ref = AsyncMock(return_value=None)
    repo.get_by_id = AsyncMock(return_value=None)
    repo.list_transactions = AsyncMock(
        return_value=InventoryTransactionPage(items=[], next_cursor=None)
    )
    return repo


@pytest.fixture
def mock_grn_repo() -> MagicMock:
    repo = MagicMock()
    repo.next_id = MagicMock(return_value=uuid.uuid4())
    repo.create = AsyncMock()
    return repo


@pytest.fixture
def mock_reconciliation_repo() -> MagicMock:
    repo = MagicMock()
    repo.next_id = MagicMock(return_value=uuid.uuid4())
    repo.create = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.approve = AsyncMock()
    return repo


# ==========================================================================
# Lazy create-on-first-use
# ==========================================================================


async def test_get_or_create_returns_existing_location(mock_location_repo: MagicMock) -> None:
    existing = MagicMock(spec=InventoryLocation)
    mock_location_repo.get_by_location_ref.return_value = existing

    use_case = GetOrCreateInventoryLocationUseCase(mock_location_repo)
    result = await use_case.execute(
        tenant_id=uuid.uuid4(), location_type="warehouse", location_ref_id=uuid.uuid4()
    )

    assert result is existing


async def test_get_or_create_synthesizes_zero_balance_location_without_saving(
    mock_location_repo: MagicMock,
) -> None:
    """A never-touched location is returned in-memory, all-zero — no `save()` call."""
    use_case = GetOrCreateInventoryLocationUseCase(mock_location_repo)
    location_ref_id = uuid.uuid4()

    result = await use_case.execute(
        tenant_id=uuid.uuid4(), location_type="vehicle", location_ref_id=location_ref_id
    )

    assert result.location_type == "vehicle"
    assert result.location_ref_id == location_ref_id
    assert result.balances == {}
    mock_location_repo.save.assert_not_called()


async def test_get_inventory_balance_never_touched_returns_all_zero_not_error(
    mock_location_repo: MagicMock,
) -> None:
    use_case = GetInventoryBalanceUseCase(mock_location_repo)
    location = await use_case.execute(
        GetInventoryBalanceQuery(
            tenant_id=uuid.uuid4(), location_type="warehouse", location_ref_id=uuid.uuid4()
        )
    )
    assert location.balances == {}


async def test_list_inventory_transactions_never_touched_returns_empty_page(
    mock_location_repo: MagicMock,
) -> None:
    use_case = ListInventoryTransactionsUseCase(mock_location_repo)
    page = await use_case.execute(
        ListInventoryTransactionsQuery(
            tenant_id=uuid.uuid4(), location_type="vehicle", location_ref_id=uuid.uuid4()
        )
    )
    assert page.items == []
    mock_location_repo.list_transactions.assert_called_once()


# ==========================================================================
# LoadTransferUseCase — atomicity
# ==========================================================================


async def test_load_transfer_moves_stock_between_both_locations(
    mock_location_repo: MagicMock, mock_uow: MagicMock
) -> None:
    tenant_id = uuid.uuid4()
    warehouse_id = uuid.uuid4()
    vehicle_id = uuid.uuid4()
    cylinder_type_id = uuid.uuid4()

    warehouse_location = InventoryLocation(
        inventory_location_id=uuid.uuid4(),
        tenant_id=tenant_id,
        location_type="warehouse",
        location_ref_id=warehouse_id,
        balances={(cylinder_type_id, "filled"): 50},
    )
    vehicle_location = InventoryLocation(
        inventory_location_id=uuid.uuid4(),
        tenant_id=tenant_id,
        location_type="vehicle",
        location_ref_id=vehicle_id,
    )

    async def _get_by_ref(
        location_type: str, location_ref_id: uuid.UUID
    ) -> InventoryLocation | None:
        if location_type == "warehouse":
            return warehouse_location
        return vehicle_location

    mock_location_repo.get_by_location_ref.side_effect = _get_by_ref

    use_case = LoadTransferUseCase(mock_location_repo, mock_uow)
    warehouse_result, vehicle_result = await use_case.execute(
        LoadTransferCommand(
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
            vehicle_id=vehicle_id,
            lines=[
                LoadTransferLine(cylinder_type_id=cylinder_type_id, status="filled", quantity=20)
            ],
            performed_by=uuid.uuid4(),
        )
    )

    assert warehouse_result.balance_of(cylinder_type_id, "filled") == 30
    assert vehicle_result.balance_of(cylinder_type_id, "filled") == 20
    assert mock_location_repo.save.call_count == 2
    mock_uow.commit.assert_called_once()


async def test_load_transfer_insufficient_stock_saves_nothing(
    mock_location_repo: MagicMock, mock_uow: MagicMock
) -> None:
    """If unload() raises partway through, load() is never reached and
    nothing is saved — BR-29's "one transaction or none."
    """
    tenant_id = uuid.uuid4()
    warehouse_id = uuid.uuid4()
    vehicle_id = uuid.uuid4()
    cylinder_type_id = uuid.uuid4()

    warehouse_location = InventoryLocation(
        inventory_location_id=uuid.uuid4(),
        tenant_id=tenant_id,
        location_type="warehouse",
        location_ref_id=warehouse_id,
    )
    vehicle_location = InventoryLocation(
        inventory_location_id=uuid.uuid4(),
        tenant_id=tenant_id,
        location_type="vehicle",
        location_ref_id=vehicle_id,
    )

    async def _get_by_ref(
        location_type: str, location_ref_id: uuid.UUID
    ) -> InventoryLocation | None:
        return warehouse_location if location_type == "warehouse" else vehicle_location

    mock_location_repo.get_by_location_ref.side_effect = _get_by_ref

    use_case = LoadTransferUseCase(mock_location_repo, mock_uow)
    with pytest.raises(InsufficientStockError):
        await use_case.execute(
            LoadTransferCommand(
                tenant_id=tenant_id,
                warehouse_id=warehouse_id,
                vehicle_id=vehicle_id,
                lines=[
                    LoadTransferLine(
                        cylinder_type_id=cylinder_type_id, status="filled", quantity=999
                    )
                ],
                performed_by=uuid.uuid4(),
            )
        )

    assert vehicle_location.balances == {}
    mock_location_repo.save.assert_not_called()
    mock_uow.commit.assert_not_called()


# ==========================================================================
# Goods receipt / status-change / adjust
# ==========================================================================


async def test_record_goods_receipt_credits_filled_and_creates_grn(
    mock_location_repo: MagicMock, mock_grn_repo: MagicMock, mock_uow: MagicMock
) -> None:
    tenant_id = uuid.uuid4()
    warehouse_id = uuid.uuid4()
    grn_entry = MagicMock(spec=GoodsReceiptNoteEntry)
    mock_grn_repo.create.return_value = grn_entry

    use_case = RecordGoodsReceiptUseCase(mock_location_repo, mock_grn_repo, mock_uow)
    result = await use_case.execute(
        RecordGoodsReceiptCommand(
            tenant_id=tenant_id,
            warehouse_id=warehouse_id,
            cylinder_type_id=uuid.uuid4(),
            quantity_received=50,
            received_by=uuid.uuid4(),
        )
    )

    assert result is grn_entry
    mock_location_repo.save.assert_called_once()
    mock_grn_repo.create.assert_called_once()
    mock_uow.commit.assert_called_once()


async def test_change_cylinder_status_invalid_transition_saves_nothing(
    mock_location_repo: MagicMock, mock_uow: MagicMock
) -> None:
    tenant_id = uuid.uuid4()
    cylinder_type_id = uuid.uuid4()
    location = InventoryLocation(
        inventory_location_id=uuid.uuid4(),
        tenant_id=tenant_id,
        location_type="warehouse",
        location_ref_id=uuid.uuid4(),
        balances={(cylinder_type_id, "filled"): 10},
    )
    mock_location_repo.get_by_location_ref.return_value = location

    use_case = ChangeCylinderStatusUseCase(mock_location_repo, mock_uow)
    with pytest.raises(InvalidStatusTransitionError):
        await use_case.execute(
            ChangeCylinderStatusCommand(
                tenant_id=tenant_id,
                location_type="warehouse",
                location_ref_id=uuid.uuid4(),
                cylinder_type_id=cylinder_type_id,
                from_status="filled",
                to_status="empty",
                quantity=5,
                performed_by=uuid.uuid4(),
            )
        )
    mock_location_repo.save.assert_not_called()
    mock_uow.commit.assert_not_called()


async def test_adjust_inventory_success(mock_location_repo: MagicMock, mock_uow: MagicMock) -> None:
    tenant_id = uuid.uuid4()
    cylinder_type_id = uuid.uuid4()
    location = InventoryLocation(
        inventory_location_id=uuid.uuid4(),
        tenant_id=tenant_id,
        location_type="warehouse",
        location_ref_id=uuid.uuid4(),
        balances={(cylinder_type_id, "filled"): 10},
    )
    mock_location_repo.get_by_location_ref.return_value = location

    use_case = AdjustInventoryUseCase(mock_location_repo, mock_uow)
    result = await use_case.execute(
        AdjustInventoryCommand(
            tenant_id=tenant_id,
            location_type="warehouse",
            location_ref_id=uuid.uuid4(),
            cylinder_type_id=cylinder_type_id,
            from_status="filled",
            to_status="leakage",
            quantity=3,
            performed_by=uuid.uuid4(),
            reason="Damaged during offload",
        )
    )

    assert result.balance_of(cylinder_type_id, "leakage") == 3
    mock_location_repo.save.assert_called_once()
    mock_uow.commit.assert_called_once()


# ==========================================================================
# Reconciliation
# ==========================================================================


async def test_create_reconciliation_record_uses_pre_reconcile_balance_as_expected(
    mock_location_repo: MagicMock, mock_reconciliation_repo: MagicMock, mock_uow: MagicMock
) -> None:
    tenant_id = uuid.uuid4()
    cylinder_type_id = uuid.uuid4()
    location = InventoryLocation(
        inventory_location_id=uuid.uuid4(),
        tenant_id=tenant_id,
        location_type="warehouse",
        location_ref_id=uuid.uuid4(),
        balances={(cylinder_type_id, "filled"): 50},
    )
    mock_location_repo.get_by_location_ref.return_value = location

    use_case = CreateReconciliationRecordUseCase(
        mock_location_repo, mock_reconciliation_repo, mock_uow
    )
    await use_case.execute(
        CreateReconciliationRecordCommand(
            tenant_id=tenant_id,
            location_type="warehouse",
            location_ref_id=uuid.uuid4(),
            cylinder_type_id=cylinder_type_id,
            status="filled",
            actual_quantity=45,
            recorded_by=uuid.uuid4(),
        )
    )

    _, kwargs = mock_reconciliation_repo.create.call_args
    assert kwargs["expected_quantity"] == 50
    assert kwargs["actual_quantity"] == 45
    assert location.balance_of(cylinder_type_id, "filled") == 45
    mock_uow.commit.assert_called_once()


async def test_approve_reconciliation_delegates_to_repository(
    mock_reconciliation_repo: MagicMock, mock_uow: MagicMock
) -> None:
    entry = MagicMock(spec=ReconciliationRecordEntry)
    mock_reconciliation_repo.approve.return_value = entry
    record_id = uuid.uuid4()
    approver_id = uuid.uuid4()

    use_case = ApproveReconciliationUseCase(mock_reconciliation_repo, mock_uow)
    result = await use_case.execute(
        ApproveReconciliationCommand(record_id=record_id, approved_by=approver_id)
    )

    assert result is entry
    mock_reconciliation_repo.approve.assert_called_once_with(record_id, approved_by=approver_id)
    mock_uow.commit.assert_called_once()
