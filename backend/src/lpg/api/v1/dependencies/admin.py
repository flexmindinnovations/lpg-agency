"""Administration dependencies (Phase 7) — repositories for every Area
A-H aggregate, pulled from the tenant-scoped `UnitOfWork` (or `Database`
directly, for the two repositories that don't use one — `StaffUserRepository`
and `AuditLogRepository`, see their own docstrings for why).

Same deliberate exception to "SQLAlchemy/infrastructure stays out of the api
layer" that `dependencies/identity.py`/`dependencies/unit_of_work.py` already
carry — see those modules' docstrings for the full rationale, including why
every type referenced by a function passed to `Depends()` is a real import
here, never `TYPE_CHECKING`-guarded.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends

from lpg.api.v1.dependencies.identity import get_current_principal
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.application.audit.ports import AuditLogRepository
from lpg.application.common.ports import UnitOfWork
from lpg.application.identity.ports import AuthenticatedPrincipal, StaffUserRepository
from lpg.application.platform.ports import FeatureFlagOverrideRepository, FeatureFlagRepository
from lpg.application.tenant.ports import (
    BranchRepository,
    CylinderTypeRepository,
    PriceListRepository,
    TenantConfigurationRepository,
    TenantRepository,
    WarehouseRepository,
)

if TYPE_CHECKING:
    from lpg.infrastructure.persistence.database import Database


def _get_database() -> Database:
    """Deferred import, same reason as `dependencies/identity.py`'s
    identical helper: `lpg.api.app` has a module-level `app = create_app()`
    side effect that must not run at import time here.
    """
    from lpg.api.app import get_app_state

    state = get_app_state()
    if state.database is None:
        msg = "Database is not configured — the application lifespan has not run."
        raise RuntimeError(msg)
    return state.database


def get_tenant_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> TenantRepository:
    from lpg.infrastructure.persistence.repositories.tenant import SqlAlchemyTenantRepository

    return SqlAlchemyTenantRepository(unit_of_work)  # type: ignore[arg-type]


def get_branch_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> BranchRepository:
    from lpg.infrastructure.persistence.repositories.tenant import SqlAlchemyBranchRepository

    return SqlAlchemyBranchRepository(unit_of_work)  # type: ignore[arg-type]


def get_warehouse_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> WarehouseRepository:
    from lpg.infrastructure.persistence.repositories.tenant import SqlAlchemyWarehouseRepository

    return SqlAlchemyWarehouseRepository(unit_of_work)  # type: ignore[arg-type]


def get_cylinder_type_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> CylinderTypeRepository:
    from lpg.infrastructure.persistence.repositories.tenant import (
        SqlAlchemyCylinderTypeRepository,
    )

    return SqlAlchemyCylinderTypeRepository(unit_of_work)  # type: ignore[arg-type]


def get_tenant_configuration_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> TenantConfigurationRepository:
    from lpg.infrastructure.persistence.repositories.tenant import (
        SqlAlchemyTenantConfigurationRepository,
    )

    return SqlAlchemyTenantConfigurationRepository(unit_of_work)  # type: ignore[arg-type]


def get_price_list_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> PriceListRepository:
    from lpg.infrastructure.persistence.repositories.tenant import SqlAlchemyPriceListRepository

    return SqlAlchemyPriceListRepository(unit_of_work)  # type: ignore[arg-type]


def get_feature_flag_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> FeatureFlagRepository:
    from lpg.infrastructure.persistence.repositories.platform import (
        SqlAlchemyFeatureFlagRepository,
    )

    return SqlAlchemyFeatureFlagRepository(unit_of_work)  # type: ignore[arg-type]


def get_feature_flag_override_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> FeatureFlagOverrideRepository:
    from lpg.infrastructure.persistence.repositories.tenant import (
        SqlAlchemyFeatureFlagOverrideRepository,
    )

    return SqlAlchemyFeatureFlagOverrideRepository(unit_of_work)  # type: ignore[arg-type]


def get_staff_user_repository(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> StaffUserRepository:
    from lpg.infrastructure.persistence.repositories.identity import (
        SqlAlchemyStaffUserRepository,
    )

    return SqlAlchemyStaffUserRepository(_get_database(), principal.tenant_id)


def get_audit_log_repository() -> AuditLogRepository:
    from lpg.infrastructure.persistence.repositories.audit import SqlAlchemyAuditLogRepository

    return SqlAlchemyAuditLogRepository(_get_database())
