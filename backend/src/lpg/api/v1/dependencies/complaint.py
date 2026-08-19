from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.application.common.ports import UnitOfWork
from lpg.application.complaint.ports import ComplaintUnitOfWork
from lpg.infrastructure.persistence.repositories.complaint import SqlAlchemyComplaintRepository


class _ComplaintUnitOfWorkWrapper:
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    @property
    def complaints(self) -> SqlAlchemyComplaintRepository:
        from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

        assert isinstance(self._uow, SqlAlchemyUnitOfWork)
        return SqlAlchemyComplaintRepository(self._uow)

    async def __aenter__(self) -> _ComplaintUnitOfWorkWrapper:
        await self._uow.__aenter__()
        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        await self._uow.__aexit__(exc_type, exc_val, exc_tb)

    async def commit(self) -> None:
        await self._uow.commit()

    async def rollback(self) -> None:
        await self._uow.rollback()


def get_complaint_unit_of_work(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> ComplaintUnitOfWork:
    return _ComplaintUnitOfWorkWrapper(unit_of_work)  # type: ignore[return-value]
