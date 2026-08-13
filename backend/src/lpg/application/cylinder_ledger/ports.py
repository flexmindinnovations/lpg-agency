import uuid
from typing import Protocol

from lpg.domain.cylinder_ledger.cylinder_ledger import CylinderLedger


class CylinderLedgerRepository(Protocol):
    """Repository protocol for CylinderLedger."""

    async def get_by_customer_id(self, tenant_id: uuid.UUID, customer_id: uuid.UUID) -> CylinderLedger:
        """Find the ledger for a specific customer.
        
        Returns a new empty ledger if one does not exist for this customer yet.
        """
        ...

    def add(self, ledger: CylinderLedger) -> None:
        """Add a new ledger to the repository."""
        ...
