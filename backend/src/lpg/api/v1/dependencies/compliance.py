"""FastAPI dependency providers for the compliance bounded context
(Weighment Part 1)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.application.common.ports import UnitOfWork
from lpg.application.compliance.ports import ScaleRepository


def get_scale_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> ScaleRepository:
    from lpg.infrastructure.persistence.repositories.compliance import (
        SqlAlchemyScaleRepository,
    )

    return SqlAlchemyScaleRepository(unit_of_work)  # type: ignore[arg-type]
