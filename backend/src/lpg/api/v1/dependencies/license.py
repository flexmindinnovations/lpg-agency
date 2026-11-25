"""License dependencies — repositories pulled from the tenant-scoped
`UnitOfWork` (same shape as `dependencies/admin.py`'s Feature Flags
providers), plus `get_license_status_checker`, which is deliberately
**not** `UnitOfWork`-backed: it's constructed straight from `AppState`
(mirroring `get_otp_store()`) so it can be used by `auth.py`'s
login/refresh endpoints, which run before any tenant context — and
therefore before any `UnitOfWork` — exists.

Same deliberate exception to "SQLAlchemy/infrastructure stays out of the api
layer" that `dependencies/identity.py`/`dependencies/admin.py` already
carry — every type referenced by a function passed to `Depends()` is a real
import here, never `TYPE_CHECKING`-guarded.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Request

from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.application.common.errors import ModuleDisabledError
from lpg.application.common.ports import UnitOfWork
from lpg.application.license.ports import (
    LicenseFeatureOverrideRepository,
    LicenseRepository,
    LicenseStatusChecker,
    LinkedDeviceRepository,
    TenantModuleSettingRepository,
)
from lpg.domain.license.modules import module_for_path

if TYPE_CHECKING:
    from lpg.api.app import AppState
    from lpg.config.settings import Settings


def _get_app_state_and_settings() -> tuple[AppState, Settings]:
    """Deferred import, same reason as `dependencies/identity.py`'s
    identical helper."""
    from lpg.api.app import get_app_state
    from lpg.config.settings import get_settings

    return get_app_state(), get_settings()


def get_license_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> LicenseRepository:
    from lpg.infrastructure.persistence.repositories.license import SqlAlchemyLicenseRepository

    return SqlAlchemyLicenseRepository(unit_of_work)  # type: ignore[arg-type]


def get_license_feature_override_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> LicenseFeatureOverrideRepository:
    from lpg.infrastructure.persistence.repositories.license import (
        SqlAlchemyLicenseFeatureOverrideRepository,
    )

    return SqlAlchemyLicenseFeatureOverrideRepository(unit_of_work)  # type: ignore[arg-type]


def get_linked_device_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> LinkedDeviceRepository:
    from lpg.infrastructure.persistence.repositories.license import (
        SqlAlchemyLinkedDeviceRepository,
    )

    return SqlAlchemyLinkedDeviceRepository(unit_of_work)  # type: ignore[arg-type]


def get_license_status_checker() -> LicenseStatusChecker:
    """Constructed straight from `AppState` — **first production wiring**
    of `RedisCacheClient` (see `RedisLicenseStatusChecker`'s own docstring).
    Used by `auth.py` (login/refresh, pre-tenant-context) and by the
    `/license/status` endpoint alike, so it deliberately does not depend on
    `get_unit_of_work`.
    """
    state, _settings = _get_app_state_and_settings()
    if state.redis is None:
        msg = "RedisClient is not configured — the application lifespan has not run."
        raise RuntimeError(msg)
    if state.database is None:
        msg = "Database is not configured — the application lifespan has not run."
        raise RuntimeError(msg)

    from lpg.infrastructure.license.license_status_cache import RedisLicenseStatusChecker
    from lpg.infrastructure.redis.cache import RedisCacheClient

    return RedisLicenseStatusChecker(RedisCacheClient(state.redis), state.database)


def get_module_setting_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> TenantModuleSettingRepository:
    from lpg.infrastructure.persistence.repositories.module_setting import (
        SqlAlchemyTenantModuleSettingRepository,
    )

    return SqlAlchemyTenantModuleSettingRepository(unit_of_work)  # type: ignore[arg-type]


async def require_module_access(
    request: Request,
    repository: Annotated[TenantModuleSettingRepository, Depends(get_module_setting_repository)],
) -> None:
    """Router dependency for every module-owned router: refuses the call
    (403 `MODULE_DISABLED`) when the path belongs to a module that a super admin
    has not switched on for the caller's agency. The path-to-module map lives in
    `lpg.domain.license.modules`, so a new route is covered by its path and
    cannot be left ungated by forgetting a decorator. Paths that belong to no
    module (Home, Notifications, Settings, Administration) always pass.
    """
    from lpg.config.settings import get_settings

    prefix = get_settings().api_v1_prefix
    path = request.url.path
    path = path.removeprefix(prefix)
    module_key = module_for_path(path)
    if module_key is None:
        return
    if module_key not in await repository.enabled_keys():
        msg = f"The {module_key} module is not enabled for your agency."
        raise ModuleDisabledError(msg, module=module_key)
