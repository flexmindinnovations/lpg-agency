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

from fastapi import Depends

from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.application.common.ports import UnitOfWork
from lpg.application.license.ports import (
    LicenseFeatureOverrideRepository,
    LicenseRepository,
    LicenseStatusChecker,
    LinkedDeviceRepository,
)

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
