import uuid
from abc import ABC, abstractmethod
from typing import Optional

from lpg.domain.complaint.complaint import Complaint

class ComplaintRepository(ABC):
    @abstractmethod
    async def save(self, complaint: Complaint) -> None:
        """Save a new or updated complaint."""

    @abstractmethod
    async def get_by_id(self, tenant_id: uuid.UUID, complaint_id: uuid.UUID) -> Optional[Complaint]:
        """Get a complaint by its ID and Tenant ID."""
