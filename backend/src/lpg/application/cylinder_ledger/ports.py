import uuid
from typing import Protocol

from lpg.domain.cylinder_ledger.cylinder_ledger import CylinderLedger


class CylinderLedgerRepository(Protocol):
    """Repository protocol for CylinderLedger."""

    async def get_by_customer_id(
        self, tenant_id: uuid.UUID, customer_id: uuid.UUID
    ) -> CylinderLedger:
        """Find the ledger for a specific customer.

        Returns a new empty ledger if one does not exist for this customer yet.
        """
        ...

    async def add(self, ledger: CylinderLedger) -> None:
        """Persist the ledger and drain its pending transactions.

        Async because the SQLAlchemy implementation flushes -- declaring it
        sync here made every call site drop an un-awaited coroutine on the
        floor, so nothing was ever written.
        """
        ...
