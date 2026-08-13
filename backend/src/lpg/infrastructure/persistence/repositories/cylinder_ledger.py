"""SQLAlchemy implementations of the cylinder ledger bounded context's repository ports.

All queries are automatically tenant-scoped via Row-Level Security (RLS).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from lpg.domain.cylinder_ledger.cylinder_ledger import CylinderLedger
from lpg.infrastructure.persistence.models.cylinder_ledger import (
    CylinderBalanceModel,
    CylinderLedgerModel,
    LedgerTransactionModel,
)

if TYPE_CHECKING:
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyCylinderLedgerRepository:
    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def get_by_customer_id(self, tenant_id: uuid.UUID, customer_id: uuid.UUID) -> CylinderLedger:
        """Find the ledger for a specific customer.
        
        Returns a new empty ledger if one does not exist for this customer yet.
        """
        stmt = (
            select(CylinderLedgerModel)
            .where(
                CylinderLedgerModel.tenant_id == tenant_id,
                CylinderLedgerModel.customer_id == customer_id,
                CylinderLedgerModel.is_deleted.is_(False)
            )
        )
        row = (await self._uow.session.execute(stmt)).scalars().first()

        if row is None:
            # Create a new empty ledger if none exists
            ledger = CylinderLedger(
                cylinder_ledger_id=self.next_id(),
                tenant_id=tenant_id,
                customer_id=customer_id,
                balances={},
                version=1,
            )
            self._uow.register_aggregate(ledger)
            return ledger

        # Load balances
        balance_stmt = select(CylinderBalanceModel).where(
            CylinderBalanceModel.cylinder_ledger_id == row.id,
            CylinderBalanceModel.is_deleted.is_(False),
        )
        balance_rows = (await self._uow.session.execute(balance_stmt)).scalars().all()
        balances = {b.cylinder_type_id: b.quantity for b in balance_rows}

        ledger = CylinderLedger(
            cylinder_ledger_id=row.id,
            tenant_id=row.tenant_id,
            customer_id=row.customer_id,
            balances=balances,
            version=row.version,
        )
        self._uow.register_aggregate(ledger)
        return ledger

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    async def add(self, ledger: CylinderLedger) -> None:
        """Save a new ledger or update an existing one to the repository."""
        # Note: In our current architecture, this method is typically called `save()` 
        # but the port named it `add()`. We stick with `add`.
        
        stmt = select(CylinderLedgerModel).where(CylinderLedgerModel.id == ledger.id)
        row = (await self._uow.session.execute(stmt)).scalars().first()

        if row is None:
            row = CylinderLedgerModel(
                id=ledger.id,
                tenant_id=ledger.tenant_id,
                customer_id=ledger.customer_id,
            )
            self._uow.session.add(row)
            await self._uow.session.flush()
        else:
            row.updated_at = datetime.now(UTC)

        balance_cache: dict[uuid.UUID, CylinderBalanceModel] = {}

        for txn in ledger.pending_transactions:
            txn_id = uuid.uuid4()
            self._uow.session.add(
                LedgerTransactionModel(
                    id=txn_id,
                    tenant_id=ledger.tenant_id,
                    cylinder_ledger_id=ledger.id,
                    cylinder_type_id=txn.cylinder_type_id,
                    transaction_type=txn.transaction_type,
                    quantity=txn.quantity,
                    reference_id=txn.reference_id,
                    reason=txn.reason,
                    performed_by=txn.performed_by,
                )
            )

            # Update the balance row that corresponds to this cylinder_type
            if txn.cylinder_type_id not in balance_cache:
                b_stmt = select(CylinderBalanceModel).where(
                    CylinderBalanceModel.cylinder_ledger_id == ledger.id,
                    CylinderBalanceModel.cylinder_type_id == txn.cylinder_type_id,
                    CylinderBalanceModel.is_deleted.is_(False),
                )
                b_row = (await self._uow.session.execute(b_stmt)).scalars().first()
                if b_row is None:
                    b_row = CylinderBalanceModel(
                        id=uuid.uuid4(),
                        tenant_id=ledger.tenant_id,
                        cylinder_ledger_id=ledger.id,
                        cylinder_type_id=txn.cylinder_type_id,
                        quantity=0,
                    )
                    self._uow.session.add(b_row)
                balance_cache[txn.cylinder_type_id] = b_row

            # Apply the transaction to the cached balance projection
            b_row = balance_cache[txn.cylinder_type_id]
            b_row.quantity += txn.quantity
            b_row.last_transaction_id = txn_id
            b_row.updated_at = datetime.now(UTC)

        # Clear pending transactions so we don't save them twice
        ledger.clear_pending_transactions()
