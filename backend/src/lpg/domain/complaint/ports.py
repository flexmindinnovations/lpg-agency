import uuid
from abc import ABC, abstractmethod

from lpg.domain.complaint.complaint import Complaint


class ComplaintRepository(ABC):
    @abstractmethod
    async def save(self, complaint: Complaint) -> None:
        """Save a new or updated complaint."""

    @abstractmethod
    async def get_by_id(self, tenant_id: uuid.UUID, complaint_id: uuid.UUID) -> Complaint | None:
        """Get a complaint by its ID and Tenant ID."""

    @abstractmethod
    async def list_complaints(
        self,
        tenant_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 50,
        status: str | None = None,
        customer_id: uuid.UUID | None = None,
    ) -> list[Complaint]:
        """List complaints for a tenant, newest first, optionally filtered."""

    @abstractmethod
    async def count_complaints(
        self,
        tenant_id: uuid.UUID,
        *,
        status: str | None = None,
        customer_id: uuid.UUID | None = None,
    ) -> int:
        """Count complaints for a tenant under the same filters as `list_complaints`."""
