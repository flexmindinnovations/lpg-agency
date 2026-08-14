from __future__ import annotations

from typing import Protocol, runtime_checkable

from lpg.application.common.ports import UnitOfWork
from lpg.domain.complaint.ports import ComplaintRepository

@runtime_checkable
class ComplaintUnitOfWork(UnitOfWork, Protocol):
    @property
    def complaints(self) -> ComplaintRepository: ...
