"""FastAPI dependency providers for the compliance bounded context
(Weighment Part 1 & 2)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from lpg.api.v1.dependencies.admin import get_tenant_configuration_repository
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.application.common.ports import UnitOfWork
from lpg.application.compliance.ports import ScaleRepository, WeighmentRecordRepository
from lpg.application.compliance.use_cases import RecordWeighmentUseCase
from lpg.application.tenant.ports import TenantConfigurationRepository


def get_scale_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> ScaleRepository:
    from lpg.infrastructure.persistence.repositories.compliance import (
        SqlAlchemyScaleRepository,
    )

    return SqlAlchemyScaleRepository(unit_of_work)  # type: ignore[arg-type]


def get_weighment_record_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> WeighmentRecordRepository:
    from lpg.infrastructure.persistence.repositories.compliance import (
        SqlAlchemyWeighmentRecordRepository,
    )

    return SqlAlchemyWeighmentRecordRepository(unit_of_work)  # type: ignore[arg-type]


def get_record_weighment_use_case(
    weighment_repository: Annotated[
        WeighmentRecordRepository, Depends(get_weighment_record_repository)
    ],
    scale_repository: Annotated[ScaleRepository, Depends(get_scale_repository)],
    tenant_config_repository: Annotated[
        TenantConfigurationRepository, Depends(get_tenant_configuration_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> RecordWeighmentUseCase:
    return RecordWeighmentUseCase(
        weighment_repository, scale_repository, tenant_config_repository, unit_of_work
    )
