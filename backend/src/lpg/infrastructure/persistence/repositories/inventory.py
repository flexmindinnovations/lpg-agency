"""SQLAlchemy implementations of the inventory bounded context's repository
ports (`lpg.application.inventory.ports`).

All queries are automatically tenant-scoped via Row-Level Security (RLS).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, literal, select, tuple_

from lpg.application.common.errors import NotFoundError
from lpg.application.inventory.ports import (
    GoodsReceiptNoteEntry,
    InventoryTransactionEntry,
    InventoryTransactionPage,
    ReconciliationRecordEntry,
)
from lpg.domain.inventory.inventory_location import InventoryLocation
from lpg.infrastructure.persistence.models.inventory import (
    GoodsReceiptNoteModel,
    InventoryBalanceModel,
    InventoryLocationModel,
    InventoryTransactionModel,
    ReconciliationRecordModel,
)

if TYPE_CHECKING:
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

_CURSOR_SEPARATOR = "|"


def _encode_cursor(performed_at: datetime, entry_id: uuid.UUID) -> str:
    return f"{performed_at.isoformat()}{_CURSOR_SEPARATOR}{entry_id}"


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    performed_at_iso, entry_id = cursor.rsplit(_CURSOR_SEPARATOR, 1)
    return datetime.fromisoformat(performed_at_iso), uuid.UUID(entry_id)


class SqlAlchemyInventoryLocationRepository:
    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def get_by_id(self, location_id: uuid.UUID) -> InventoryLocation | None:
        stmt = select(InventoryLocationModel).where(
            InventoryLocationModel.id == location_id,
            InventoryLocationModel.is_deleted.is_(False),
        )
        row = (await self._uow.session.execute(stmt)).scalars().first()
        return await self._to_domain(row) if row is not None else None

    async def get_by_location_ref(
        self, location_type: str, location_ref_id: uuid.UUID
    ) -> InventoryLocation | None:
        stmt = select(InventoryLocationModel).where(
            InventoryLocationModel.location_type == location_type,
            InventoryLocationModel.location_ref_id == location_ref_id,
            InventoryLocationModel.is_deleted.is_(False),
        )
        row = (await self._uow.session.execute(stmt)).scalars().first()
        return await self._to_domain(row) if row is not None else None

    async def _to_domain(self, row: InventoryLocationModel) -> InventoryLocation:
        balance_stmt = select(InventoryBalanceModel).where(
            InventoryBalanceModel.inventory_location_id == row.id,
            InventoryBalanceModel.is_deleted.is_(False),
        )
        balance_rows = (await self._uow.session.execute(balance_stmt)).scalars().all()
        balances = {(b.cylinder_type_id, b.status): b.quantity for b in balance_rows}

        location = InventoryLocation(
            inventory_location_id=row.id,
            tenant_id=row.tenant_id,
            location_type=row.location_type,
            location_ref_id=row.location_ref_id,
            balances=balances,
            version=row.version,
        )
        self._uow.register_aggregate(location)
        return location

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    async def save(self, location: InventoryLocation) -> None:
        stmt = select(InventoryLocationModel).where(InventoryLocationModel.id == location.id)
        row = (await self._uow.session.execute(stmt)).scalars().first()

        if row is None:
            row = InventoryLocationModel(
                id=location.id,
                tenant_id=location.tenant_id,
                location_type=location.location_type,
                location_ref_id=location.location_ref_id,
            )
            self._uow.session.add(row)
            # Flush now so the location row is INSERTed before any
            # transaction/balance rows that FK-reference it — cross-table
            # insert ordering within one flush is not reliably inferred
            # from bare column-level ForeignKey()s without an explicit
            # relationship(), so this is not just a performance nicety.
            await self._uow.session.flush()
        else:
            row.updated_at = datetime.now(UTC)

        # Write each transaction row first, then upsert the balance row(s)
        # it justifies, in the same flush — the "materialized projection
        # only updated within the same transaction as its source" rule.
        # `balance_cache` tracks rows already created/loaded *this call* —
        # the session has `autoflush=False`, so a `session.add()`'d row is
        # not yet visible to a subsequent SELECT, and two pending
        # transactions can legitimately touch the same (cylinder_type,
        # status) key (e.g. receive_goods then unload, both crediting/
        # debiting "filled" before the first save()) — without the cache,
        # the second upsert's SELECT would miss the first's unflushed
        # INSERT and attempt a duplicate row, violating uq_inventory_balance.
        balance_cache: dict[tuple[uuid.UUID, str], InventoryBalanceModel] = {}

        for txn in location.pending_transactions:
            txn_id = uuid.uuid4()
            self._uow.session.add(
                InventoryTransactionModel(
                    id=txn_id,
                    tenant_id=location.tenant_id,
                    inventory_location_id=location.id,
                    cylinder_type_id=txn.cylinder_type_id,
                    transaction_type=txn.transaction_type,
                    from_status=txn.from_status,
                    to_status=txn.to_status,
                    quantity=txn.quantity,
                    reference_order_id=txn.reference_order_id,
                    reason=txn.reason,
                    performed_by=txn.performed_by,
                )
            )
            # Flush so the transaction row is INSERTed before the balance
            # row(s) that FK-reference it via `last_transaction_id` — same
            # cross-table ordering reasoning as the location flush above.
            await self._uow.session.flush()
            await self._upsert_balance(
                location, balance_cache, txn.cylinder_type_id, txn.to_status, txn_id
            )
            # from_status differs from to_status only for change_status/
            # adjust — receive_goods/unload/load/delivery/collection/
            # reconciliation always set from_status == to_status, so the
            # branch above already covers the only balance row touched.
            if txn.from_status is not None and txn.from_status != txn.to_status:
                await self._upsert_balance(
                    location, balance_cache, txn.cylinder_type_id, txn.from_status, txn_id
                )

        location.clear_pending_transactions()

    async def _upsert_balance(
        self,
        location: InventoryLocation,
        balance_cache: dict[tuple[uuid.UUID, str], InventoryBalanceModel],
        cylinder_type_id: uuid.UUID,
        status: str,
        last_transaction_id: uuid.UUID,
    ) -> None:
        key = (cylinder_type_id, status)
        balance_row = balance_cache.get(key)
        if balance_row is None:
            stmt = select(InventoryBalanceModel).where(
                InventoryBalanceModel.inventory_location_id == location.id,
                InventoryBalanceModel.cylinder_type_id == cylinder_type_id,
                InventoryBalanceModel.status == status,
            )
            balance_row = (await self._uow.session.execute(stmt)).scalars().first()

        quantity = location.balance_of(cylinder_type_id, status)

        if balance_row is None:
            balance_row = InventoryBalanceModel(
                id=uuid.uuid4(),
                tenant_id=location.tenant_id,
                inventory_location_id=location.id,
                cylinder_type_id=cylinder_type_id,
                status=status,
                quantity=quantity,
                last_transaction_id=last_transaction_id,
            )
            self._uow.session.add(balance_row)
        else:
            balance_row.quantity = quantity
            balance_row.last_transaction_id = last_transaction_id
            balance_row.updated_at = datetime.now(UTC)
            # `version` is None on a row this same call just created but
            # hasn't flushed yet (server_default only applies at INSERT) —
            # leave it for the default to set rather than incrementing None.
            if balance_row.version is not None:
                balance_row.version += 1

        balance_cache[key] = balance_row

    # ------------------------------------------------------------------
    # Transaction history
    # ------------------------------------------------------------------

    async def list_transactions(
        self,
        location_id: uuid.UUID,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> InventoryTransactionPage:
        stmt = (
            select(InventoryTransactionModel)
            .where(InventoryTransactionModel.inventory_location_id == location_id)
            .order_by(
                InventoryTransactionModel.performed_at.desc(), InventoryTransactionModel.id.desc()
            )
            .limit(limit + 1)
        )
        if cursor is not None:
            cursor_performed_at, cursor_id = _decode_cursor(cursor)
            stmt = stmt.where(
                tuple_(InventoryTransactionModel.performed_at, InventoryTransactionModel.id)
                < tuple_(literal(cursor_performed_at), literal(cursor_id))
            )

        rows = list((await self._uow.session.execute(stmt)).scalars())
        has_next = len(rows) > limit
        page_rows = rows[:limit]
        next_cursor = (
            _encode_cursor(page_rows[-1].performed_at, page_rows[-1].id)
            if has_next and page_rows
            else None
        )
        return InventoryTransactionPage(
            items=[self._transaction_to_entry(row) for row in page_rows],
            next_cursor=next_cursor,
        )

    async def get_balance_summary(self) -> dict[str, int]:
        stmt = (
            select(InventoryBalanceModel.status, func.sum(InventoryBalanceModel.quantity))
            .where(InventoryBalanceModel.is_deleted.is_(False))
            .group_by(InventoryBalanceModel.status)
        )
        result = await self._uow.session.execute(stmt)
        return {status: int(total) for status, total in result.all()}

    @staticmethod
    def _transaction_to_entry(row: InventoryTransactionModel) -> InventoryTransactionEntry:
        return InventoryTransactionEntry(
            id=row.id,
            tenant_id=row.tenant_id,
            inventory_location_id=row.inventory_location_id,
            cylinder_type_id=row.cylinder_type_id,
            transaction_type=row.transaction_type,
            from_status=row.from_status,
            to_status=row.to_status,
            quantity=row.quantity,
            reference_order_id=row.reference_order_id,
            reason=row.reason,
            performed_by=row.performed_by,
            performed_at=row.performed_at,
        )


class SqlAlchemyGoodsReceiptNoteRepository:
    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    async def create(
        self,
        *,
        grn_id: uuid.UUID,
        tenant_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        cylinder_type_id: uuid.UUID,
        quantity_received: int,
        source_omc: str | None,
        received_by: uuid.UUID,
        grn_number: str,
    ) -> GoodsReceiptNoteEntry:
        row = GoodsReceiptNoteModel(
            id=grn_id,
            tenant_id=tenant_id,
            grn_number=grn_number,
            warehouse_id=warehouse_id,
            cylinder_type_id=cylinder_type_id,
            quantity_received=quantity_received,
            source_omc=source_omc,
            received_by=received_by,
        )
        self._uow.session.add(row)
        await self._uow.session.flush()
        return GoodsReceiptNoteEntry(
            id=row.id,
            tenant_id=row.tenant_id,
            warehouse_id=row.warehouse_id,
            cylinder_type_id=row.cylinder_type_id,
            quantity_received=row.quantity_received,
            source_omc=row.source_omc,
            received_by=row.received_by,
            received_at=row.received_at,
            grn_number=row.grn_number,
        )


class SqlAlchemyReconciliationRecordRepository:
    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    async def create(
        self,
        *,
        record_id: uuid.UUID,
        tenant_id: uuid.UUID,
        inventory_location_id: uuid.UUID,
        cylinder_type_id: uuid.UUID,
        status: str,
        expected_quantity: int,
        actual_quantity: int,
        recorded_by: uuid.UUID,
    ) -> ReconciliationRecordEntry:
        row = ReconciliationRecordModel(
            id=record_id,
            tenant_id=tenant_id,
            inventory_location_id=inventory_location_id,
            cylinder_type_id=cylinder_type_id,
            status=status,
            expected_quantity=expected_quantity,
            actual_quantity=actual_quantity,
            recorded_by=recorded_by,
        )
        self._uow.session.add(row)
        await self._uow.session.flush()
        return self._to_entry(row)

    async def get_by_id(self, record_id: uuid.UUID) -> ReconciliationRecordEntry | None:
        stmt = select(ReconciliationRecordModel).where(
            ReconciliationRecordModel.id == record_id,
            ReconciliationRecordModel.is_deleted.is_(False),
        )
        row = (await self._uow.session.execute(stmt)).scalars().first()
        return self._to_entry(row) if row is not None else None

    async def get_latest_for_location(
        self, inventory_location_id: uuid.UUID
    ) -> ReconciliationRecordEntry | None:
        stmt = (
            select(ReconciliationRecordModel)
            .where(
                ReconciliationRecordModel.inventory_location_id == inventory_location_id,
                ReconciliationRecordModel.is_deleted.is_(False),
            )
            .order_by(ReconciliationRecordModel.created_at.desc())
            .limit(1)
        )
        row = (await self._uow.session.execute(stmt)).scalars().first()
        return self._to_entry(row) if row is not None else None

    async def approve(
        self, record_id: uuid.UUID, *, approved_by: uuid.UUID
    ) -> ReconciliationRecordEntry:
        stmt = select(ReconciliationRecordModel).where(
            ReconciliationRecordModel.id == record_id,
            ReconciliationRecordModel.is_deleted.is_(False),
        )
        row = (await self._uow.session.execute(stmt)).scalars().first()
        if row is None:
            msg = f"Reconciliation record {record_id} not found."
            raise NotFoundError(msg)

        row.approved_by = approved_by
        row.approved_at = datetime.now(UTC)
        row.updated_at = datetime.now(UTC)
        row.version += 1
        await self._uow.session.flush()
        # An UPDATE (unlike the INSERT in create()) doesn't get its
        # Computed() `variance` value back via RETURNING, so SQLAlchemy
        # expires it — read it back explicitly, in-context, rather than
        # letting `_to_entry` trigger an implicit lazy-load that fails
        # with MissingGreenlet outside an active async DB call.
        await self._uow.session.refresh(row)
        return self._to_entry(row)

    @staticmethod
    def _to_entry(row: ReconciliationRecordModel) -> ReconciliationRecordEntry:
        return ReconciliationRecordEntry(
            id=row.id,
            tenant_id=row.tenant_id,
            inventory_location_id=row.inventory_location_id,
            cylinder_type_id=row.cylinder_type_id,
            status=row.status,
            expected_quantity=row.expected_quantity,
            actual_quantity=row.actual_quantity,
            variance=row.variance,
            recorded_by=row.recorded_by,
            approved_by=row.approved_by,
            approved_at=row.approved_at,
        )
