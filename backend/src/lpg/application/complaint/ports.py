from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from lpg.application.common.ports import UnitOfWork

if TYPE_CHECKING:
    from lpg.domain.complaint.ports import ComplaintRepository


@runtime_checkable
class ComplaintUnitOfWork(UnitOfWork, Protocol):
    @property
    def complaints(self) -> ComplaintRepository: ...
