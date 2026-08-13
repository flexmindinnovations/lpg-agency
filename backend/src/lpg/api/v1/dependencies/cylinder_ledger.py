from typing import Annotated

from fastapi import Depends

from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.application.common.ports import UnitOfWork
from lpg.application.cylinder_ledger.ports import CylinderLedgerRepository
from lpg.application.cylinder_ledger.use_cases import (
    AdjustLedgerBalanceUseCase,
    GetCylinderLedgerUseCase,
)
from lpg.infrastructure.persistence.repositories.cylinder_ledger import (
    SqlAlchemyCylinderLedgerRepository,
)


def get_cylinder_ledger_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> CylinderLedgerRepository:
    return SqlAlchemyCylinderLedgerRepository(unit_of_work)  # type: ignore[arg-type]


def get_adjust_ledger_balance_use_case(
    repository: Annotated[CylinderLedgerRepository, Depends(get_cylinder_ledger_repository)],
) -> AdjustLedgerBalanceUseCase:
    return AdjustLedgerBalanceUseCase(repository)


def get_cylinder_ledger_use_case(
    repository: Annotated[CylinderLedgerRepository, Depends(get_cylinder_ledger_repository)],
) -> GetCylinderLedgerUseCase:
    return GetCylinderLedgerUseCase(repository)
