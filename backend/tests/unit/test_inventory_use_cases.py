"""Unit tests for inventory use cases.

Uses mocked repositories and UoW — no database required.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from lpg.application.common.errors import ValidationError
from lpg.application.inventory.ports import (
    GoodsReceiptNoteEntry,
    InventoryTransactionPage,
    LedgerMovement,
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
    GetStockRegisterQuery,
    GetStockRegisterUseCase,
    ListInventoryTransactionsQuery,
    ListInventoryTransactionsUseCase,
    LoadTransferCommand,
    LoadTransferLine,
    LoadTransferUseCase,
    RecordGoodsReceiptCommand,
    RecordGoodsReceiptUseCase,
    RejectReconciliationCommand,
    RejectReconciliationUseCase,
)
from lpg.domain.inventory.inventory_location import (
    InsufficientStockError,
    InvalidStatusTransitionError,
    InventoryLocation,
)
from lpg.domain.inventory.reconciliation import (
    ReconciliationAlreadyDecidedError,
    SelfApprovalNotAllowedError,
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
    repo.get_for_decision = AsyncMock(return_value=None)
    repo.mark_approved = AsyncMock()
    repo.mark_rejected = AsyncMock()
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
    mock_grn_number_sequence = MagicMock()
    mock_grn_number_sequence.next = AsyncMock(return_value="GRN000001")

    use_case = RecordGoodsReceiptUseCase(
        mock_location_repo, mock_grn_repo, mock_uow, mock_grn_number_sequence
    )
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


async def test_create_reconciliation_record_does_not_change_stock(
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
    assert location.balance_of(cylinder_type_id, "filled") == 50
    assert location.pending_transactions == ()
    mock_uow.commit.assert_called_once()


def _pending_record(
    *,
    location_id: uuid.UUID,
    cylinder_type_id: uuid.UUID,
    recorded_by: uuid.UUID,
    expected: int = 50,
    actual: int = 45,
    approved_at: datetime | None = None,
) -> ReconciliationRecordEntry:
    return ReconciliationRecordEntry(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        inventory_location_id=location_id,
        cylinder_type_id=cylinder_type_id,
        status="filled",
        expected_quantity=expected,
        actual_quantity=actual,
        variance=actual - expected,
        recorded_by=recorded_by,
        approved_by=None,
        approved_at=approved_at,
    )


def _warehouse(cylinder_type_id: uuid.UUID, filled: int) -> InventoryLocation:
    return InventoryLocation(
        inventory_location_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        location_type="warehouse",
        location_ref_id=uuid.uuid4(),
        balances={(cylinder_type_id, "filled"): filled},
    )


async def test_approve_books_the_variance_once(
    mock_location_repo: MagicMock, mock_reconciliation_repo: MagicMock, mock_uow: MagicMock
) -> None:
    cylinder_type_id = uuid.uuid4()
    location = _warehouse(cylinder_type_id, 50)
    record = _pending_record(
        location_id=location.id, cylinder_type_id=cylinder_type_id, recorded_by=uuid.uuid4()
    )
    mock_reconciliation_repo.get_for_decision.return_value = record
    mock_location_repo.get_by_id.return_value = location
    approver_id = uuid.uuid4()

    use_case = ApproveReconciliationUseCase(mock_reconciliation_repo, mock_location_repo, mock_uow)
    await use_case.execute(
        ApproveReconciliationCommand(record_id=record.id, approved_by=approver_id)
    )

    assert location.balance_of(cylinder_type_id, "filled") == 45
    mock_reconciliation_repo.mark_approved.assert_called_once_with(
        record.id, approved_by=approver_id
    )
    mock_uow.commit.assert_called_once()


async def test_the_counter_cannot_approve_their_own_count(
    mock_location_repo: MagicMock, mock_reconciliation_repo: MagicMock, mock_uow: MagicMock
) -> None:
    counter = uuid.uuid4()
    cylinder_type_id = uuid.uuid4()
    location = _warehouse(cylinder_type_id, 50)
    record = _pending_record(
        location_id=location.id, cylinder_type_id=cylinder_type_id, recorded_by=counter
    )
    mock_reconciliation_repo.get_for_decision.return_value = record
    mock_location_repo.get_by_id.return_value = location

    use_case = ApproveReconciliationUseCase(mock_reconciliation_repo, mock_location_repo, mock_uow)
    with pytest.raises(SelfApprovalNotAllowedError):
        await use_case.execute(
            ApproveReconciliationCommand(record_id=record.id, approved_by=counter)
        )

    assert location.balance_of(cylinder_type_id, "filled") == 50
    mock_uow.commit.assert_not_called()


async def test_an_approved_count_cannot_be_approved_again(
    mock_location_repo: MagicMock, mock_reconciliation_repo: MagicMock, mock_uow: MagicMock
) -> None:
    cylinder_type_id = uuid.uuid4()
    location = _warehouse(cylinder_type_id, 45)
    record = _pending_record(
        location_id=location.id,
        cylinder_type_id=cylinder_type_id,
        recorded_by=uuid.uuid4(),
        approved_at=datetime.now(UTC),
    )
    mock_reconciliation_repo.get_for_decision.return_value = record
    mock_location_repo.get_by_id.return_value = location

    use_case = ApproveReconciliationUseCase(mock_reconciliation_repo, mock_location_repo, mock_uow)
    with pytest.raises(ReconciliationAlreadyDecidedError):
        await use_case.execute(
            ApproveReconciliationCommand(record_id=record.id, approved_by=uuid.uuid4())
        )
    assert location.balance_of(cylinder_type_id, "filled") == 45


async def test_reject_leaves_stock_alone(
    mock_reconciliation_repo: MagicMock, mock_uow: MagicMock
) -> None:
    record = _pending_record(
        location_id=uuid.uuid4(), cylinder_type_id=uuid.uuid4(), recorded_by=uuid.uuid4()
    )
    mock_reconciliation_repo.get_for_decision.return_value = record
    rejecter = uuid.uuid4()

    await RejectReconciliationUseCase(mock_reconciliation_repo, mock_uow).execute(
        RejectReconciliationCommand(record_id=record.id, rejected_by=rejecter, reason="Recount")
    )

    mock_reconciliation_repo.mark_rejected.assert_called_once_with(
        record.id, rejected_by=rejecter, reason="Recount"
    )
    mock_uow.commit.assert_called_once()


# ==========================================================================
# Goods receipt: OMC is a validated code
# ==========================================================================


async def test_goods_receipt_normalises_the_omc_and_rejects_unknown_ones(
    mock_location_repo: MagicMock, mock_grn_repo: MagicMock, mock_uow: MagicMock
) -> None:
    sequence = MagicMock()
    sequence.next = AsyncMock(return_value="GRN000001")
    use_case = RecordGoodsReceiptUseCase(mock_location_repo, mock_grn_repo, mock_uow, sequence)
    base: dict[str, Any] = {
        "tenant_id": uuid.uuid4(),
        "warehouse_id": uuid.uuid4(),
        "cylinder_type_id": uuid.uuid4(),
        "quantity_received": 12,
        "received_by": uuid.uuid4(),
    }

    await use_case.execute(
        RecordGoodsReceiptCommand(**base, source_omc="IOCL", truck_number=" ts09 ua 3320 ")
    )
    _, kwargs = mock_grn_repo.create.call_args
    assert kwargs["source_omc"] == "iocl"
    assert kwargs["truck_number"] == "TS09 UA 3320"

    with pytest.raises(ValidationError):
        await use_case.execute(RecordGoodsReceiptCommand(**base, source_omc="Indane"))


# ==========================================================================
# Stock register
# ==========================================================================


async def test_stock_register_walks_back_from_todays_balance(
    mock_location_repo: MagicMock,
) -> None:
    cylinder_type_id = uuid.uuid4()
    location = _warehouse(cylinder_type_id, 110)
    mock_location_repo.get_by_location_ref.return_value = location
    day1, day2 = date(2026, 10, 19), date(2026, 10, 20)
    mock_location_repo.list_movements_since = AsyncMock(
        return_value=[
            LedgerMovement(day1, cylinder_type_id, "grn_receipt", None, "filled", 100),
            LedgerMovement(day1, cylinder_type_id, "unload", "filled", "filled", 30),
            LedgerMovement(day2, cylinder_type_id, "unload", "filled", "filled", 20),
        ]
    )

    lines = await GetStockRegisterUseCase(mock_location_repo).execute(
        GetStockRegisterQuery(
            tenant_id=uuid.uuid4(),
            location_type="warehouse",
            location_ref_id=uuid.uuid4(),
            date_from=day1,
            date_to=day2,
            today=day2,
        )
    )

    assert [(ln.opening, ln.receipts, ln.issues, ln.closing) for ln in lines] == [
        (60, 100, 30, 130),
        (130, 0, 20, 110),
    ]


async def test_stock_register_refuses_a_backwards_range(mock_location_repo: MagicMock) -> None:
    with pytest.raises(ValidationError):
        await GetStockRegisterUseCase(mock_location_repo).execute(
            GetStockRegisterQuery(
                tenant_id=uuid.uuid4(),
                location_type="warehouse",
                location_ref_id=uuid.uuid4(),
                date_from=date(2026, 10, 20),
                date_to=date(2026, 10, 19),
                today=date(2026, 10, 20),
            )
        )
