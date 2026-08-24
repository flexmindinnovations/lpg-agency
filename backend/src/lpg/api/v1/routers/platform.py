"""The Platform Console — `super_admin` control plane, mounted under
`/platform`, architecturally separate from `/admin` (tenant-scoped
administration, plus the platform-tier License/Feature-Flags routes that
used to live there before this router existed).

Every route here is gated by `require_platform_permission`/
`require_live_platform_permission` (`api/v1/dependencies/platform.py`) —
never `require_permission`/`require_live_permission`, which resolve a
`TenantContext` a `PlatformPrincipal` (JWT with no `tenant_id` claim, only
ever `super_admin`) structurally cannot provide. Repositories are
constructed inline, per request, from `get_platform_unit_of_work_factory` —
never `Depends(get_*_repository)` the way tenant-scoped routers do, since
each platform write targets an explicit tenant supplied by the request
itself (path/body), not derivable from the caller's own JWT
(`dependencies/platform.py`'s own docstring has the full reasoning).

**Every type used inside `Annotated[X, Depends(...)]` below is a real
import, never `TYPE_CHECKING`-guarded** — same FastAPI footgun
`api/v1/routers/auth.py`'s module docstring warns about.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends

from lpg.api.v1.dependencies.identity import get_token_hasher
from lpg.api.v1.dependencies.license import get_license_status_checker
from lpg.api.v1.dependencies.platform import (
    get_platform_principal,
    get_platform_unit_of_work_factory,
    require_live_platform_permission,
)
from lpg.api.v1.schemas.admin import (
    CreateFeatureFlagRequest,
    FeatureFlagResponse,
    ScheduleFeatureFlagRequest,
    SetFeatureFlagEnabledByDefaultRequest,
    SetFeatureFlagRolloutPercentageRequest,
    TenantResponse,
)
from lpg.api.v1.schemas.identity import PrincipalResponse
from lpg.api.v1.schemas.license import (
    ActivateLicenseRequest,
    IssuedLicenseResponse,
    IssueLicenseRequest,
    LicenseResponse,
    SetLicenseDeviceCapRequest,
    SetLicenseFeatureOverrideRequest,
    SetLicensePlanTierRequest,
)
from lpg.application.common.ports import UnitOfWork
from lpg.application.identity.ports import TokenHasher
from lpg.application.license.activate_license import (
    ActivateLicenseCommand,
    ActivateLicenseUseCase,
)
from lpg.application.license.entitlement import (
    SetLicenseFeatureOverrideCommand,
    SetLicenseFeatureOverrideUseCase,
)
from lpg.application.license.issue_license import (
    IssueLicenseCommand,
    IssueLicenseUseCase,
    ListLicensesQuery,
    ListLicensesUseCase,
    RevokeLicenseCommand,
    RevokeLicenseUseCase,
    SetLicenseDeviceCapCommand,
    SetLicenseDeviceCapUseCase,
    SetLicensePlanTierCommand,
    SetLicensePlanTierUseCase,
)
from lpg.application.license.ports import LicenseStatusChecker
from lpg.application.platform.feature_flag import (
    CreateFeatureFlagCommand,
    CreateFeatureFlagUseCase,
    ListFeatureFlagsQuery,
    ListFeatureFlagsUseCase,
    ScheduleFeatureFlagCommand,
    ScheduleFeatureFlagUseCase,
    SetFeatureFlagEnabledByDefaultCommand,
    SetFeatureFlagEnabledByDefaultUseCase,
    SetFeatureFlagRolloutPercentageCommand,
    SetFeatureFlagRolloutPercentageUseCase,
)
from lpg.application.platform.principal import PlatformPrincipal
from lpg.application.tenant.manage_lifecycle import (
    CloseTenantCommand,
    CloseTenantUseCase,
    ListTenantsQuery,
    ListTenantsUseCase,
    ReactivateTenantCommand,
    ReactivateTenantUseCase,
    SuspendTenantCommand,
    SuspendTenantUseCase,
)
from lpg.domain.license.license import License
from lpg.domain.tenant.tenant import Tenant
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.repositories.license import (
    SqlAlchemyLicenseFeatureOverrideRepository,
    SqlAlchemyLicenseRepository,
)
from lpg.infrastructure.persistence.repositories.platform import SqlAlchemyFeatureFlagRepository
from lpg.infrastructure.persistence.repositories.tenant import SqlAlchemyTenantRepository
from lpg.infrastructure.redis.cache import RedisCacheClient
from lpg.infrastructure.tenant.tenant_status_cache import RedisTenantStatusChecker

router = APIRouter(prefix="/platform", tags=["Platform Console"])

#: Every platform write/read opens its own `UnitOfWork` scoped to an
#: explicit target tenant (or `None` for a cross-tenant list) — see
#: `get_platform_unit_of_work_factory`'s own docstring for why.
_UowFactory = Callable[[uuid.UUID | None], AbstractAsyncContextManager[UnitOfWork]]


def _license_response(license: License, *, tenant_name: str | None = None) -> LicenseResponse:
    return LicenseResponse(
        tenant_id=str(license.tenant_id),
        tenant_name=tenant_name,
        status=license.compute_status(at=datetime.now(UTC)).value,
        plan_tier=license.plan_tier,
        key_prefix=license.key_prefix,
        device_caps=license.device_caps,
        issued_at=license.issued_at,
        activated_at=license.activated_at,
        expires_at=license.expires_at,
        grace_ends_at=license.grace_ends_at,
        revoked_at=license.revoked_at,
    )


def _tenant_response(tenant: Tenant) -> TenantResponse:
    return TenantResponse(
        id=str(tenant.id),
        name=tenant.name,
        slug=tenant.slug,
        status=tenant.status,
        subscription_plan=tenant.subscription_plan,
        primary_contact_email=tenant.primary_contact_email,
        country=tenant.country,
    )


# -- Session -------------------------------------------------------------------------


@router.get(
    "/me", response_model=PrincipalResponse, summary="The current Super Admin session"
)
async def me(
    principal: Annotated[PlatformPrincipal, Depends(get_platform_principal)],
) -> PrincipalResponse:
    """The `/platform` sibling of `GET /auth/me` — the Dashboard's login
    flow calls whichever of the two matches the JWT's `role` claim
    (`AuthService.hydrateSession()`), since `/auth/me` 401s outright for a
    genuine `tenant_id = NULL` session (`JwtTenantResolver.resolve()`).

    Claims-only, same tier as `/auth/me`'s own `get_current_principal` — no
    live re-check against `identity_user_permission` here either; both
    endpoints exist to describe the session to the UI, not to gate a
    sensitive action.
    """
    return PrincipalResponse(
        user_id=str(principal.user_id),
        tenant_id=None,
        role=principal.role,
        permissions=sorted(principal.permission_codes),
        email=principal.email,
    )


# -- Agencies (tenants) -------------------------------------------------------------
#
# Metadata only — name, slug, status, plan. Never tenant business data
# (orders/customers/invoices) — explicitly out of scope for a super_admin
# session, confirmed with the user.


@router.get(
    "/agencies", response_model=list[TenantResponse], summary="List every agency (tenant)"
)
async def list_agencies(
    _principal: Annotated[
        PlatformPrincipal, Depends(require_live_platform_permission("tenant:manage_platform"))
    ],
    uow_factory: Annotated[_UowFactory, Depends(get_platform_unit_of_work_factory)],
) -> list[TenantResponse]:
    async with uow_factory(None) as uow:
        repository = SqlAlchemyTenantRepository(uow)  # type: ignore[arg-type]
        use_case = ListTenantsUseCase(repository)
        tenants = await use_case.execute(ListTenantsQuery())
        return [_tenant_response(tenant) for tenant in tenants]


@router.patch(
    "/agencies/{tenant_id}/suspend", status_code=204, summary="Suspend an agency"
)
async def suspend_agency(
    tenant_id: str,
    _principal: Annotated[
        PlatformPrincipal, Depends(require_live_platform_permission("tenant:manage_platform"))
    ],
    uow_factory: Annotated[_UowFactory, Depends(get_platform_unit_of_work_factory)],
) -> None:
    target_tenant_id = uuid.UUID(tenant_id)
    async with uow_factory(target_tenant_id) as uow:
        repository = SqlAlchemyTenantRepository(uow)  # type: ignore[arg-type]
        status_checker = RedisTenantStatusChecker(_get_redis_cache(), _get_database())
        use_case = SuspendTenantUseCase(repository, status_checker, uow)
        await use_case.execute(SuspendTenantCommand(tenant_id=target_tenant_id))


@router.patch(
    "/agencies/{tenant_id}/reactivate", status_code=204, summary="Reactivate a suspended agency"
)
async def reactivate_agency(
    tenant_id: str,
    _principal: Annotated[
        PlatformPrincipal, Depends(require_live_platform_permission("tenant:manage_platform"))
    ],
    uow_factory: Annotated[_UowFactory, Depends(get_platform_unit_of_work_factory)],
) -> None:
    target_tenant_id = uuid.UUID(tenant_id)
    async with uow_factory(target_tenant_id) as uow:
        repository = SqlAlchemyTenantRepository(uow)  # type: ignore[arg-type]
        status_checker = RedisTenantStatusChecker(_get_redis_cache(), _get_database())
        use_case = ReactivateTenantUseCase(repository, status_checker, uow)
        await use_case.execute(ReactivateTenantCommand(tenant_id=target_tenant_id))


@router.patch(
    "/agencies/{tenant_id}/close",
    status_code=204,
    summary="Close an agency permanently",
)
async def close_agency(
    tenant_id: str,
    _principal: Annotated[
        PlatformPrincipal, Depends(require_live_platform_permission("tenant:manage_platform"))
    ],
    uow_factory: Annotated[_UowFactory, Depends(get_platform_unit_of_work_factory)],
) -> None:
    target_tenant_id = uuid.UUID(tenant_id)
    async with uow_factory(target_tenant_id) as uow:
        repository = SqlAlchemyTenantRepository(uow)  # type: ignore[arg-type]
        status_checker = RedisTenantStatusChecker(_get_redis_cache(), _get_database())
        use_case = CloseTenantUseCase(repository, status_checker, uow)
        await use_case.execute(CloseTenantCommand(tenant_id=target_tenant_id))


# -- License (platform-tier — relocated from /admin/license/*) ----------------------


@router.post(
    "/license",
    response_model=IssuedLicenseResponse,
    status_code=201,
    summary="Issue a license for a tenant",
)
async def issue_license(
    body: IssueLicenseRequest,
    _principal: Annotated[
        PlatformPrincipal, Depends(require_live_platform_permission("license:manage_platform"))
    ],
    uow_factory: Annotated[_UowFactory, Depends(get_platform_unit_of_work_factory)],
    token_hasher: Annotated[TokenHasher, Depends(get_token_hasher)],
) -> IssuedLicenseResponse:
    target_tenant_id = uuid.UUID(body.tenant_id)
    async with uow_factory(target_tenant_id) as uow:
        repository = SqlAlchemyLicenseRepository(uow)  # type: ignore[arg-type]
        use_case = IssueLicenseUseCase(repository, token_hasher, uow)
        license_, plaintext_key = await use_case.execute(
            IssueLicenseCommand(
                tenant_id=target_tenant_id,
                plan_tier=body.plan_tier,
                validity_period=timedelta(days=body.validity_days),
                device_caps=body.device_caps,
            )
        )
    return IssuedLicenseResponse(
        tenant_id=str(license_.tenant_id),
        plaintext_key=plaintext_key,
        key_prefix=license_.key_prefix,
        plan_tier=license_.plan_tier,
        issued_at=license_.issued_at,
    )


@router.post(
    "/license/{tenant_id}/activate",
    response_model=LicenseResponse,
    summary="Activate a tenant's license on its behalf",
)
async def activate_license(
    tenant_id: str,
    body: ActivateLicenseRequest,
    _principal: Annotated[
        PlatformPrincipal, Depends(require_live_platform_permission("license:manage_platform"))
    ],
    uow_factory: Annotated[_UowFactory, Depends(get_platform_unit_of_work_factory)],
    token_hasher: Annotated[TokenHasher, Depends(get_token_hasher)],
    status_checker: Annotated[LicenseStatusChecker, Depends(get_license_status_checker)],
) -> LicenseResponse:
    """The `/platform` sibling of `POST /admin/license/activate`
    (`routers/admin.py`) — same `ActivateLicenseUseCase`, unchanged (D-2:
    it already takes an explicit `tenant_id`, never derived the caller's
    own), just supplied the *target* tenant from the path instead of a
    tenant-scoped principal. Lets a super_admin activate immediately after
    issuing, rather than waiting on the tenant's own self-service flow.
    """
    target_tenant_id = uuid.UUID(tenant_id)
    async with uow_factory(target_tenant_id) as uow:
        repository = SqlAlchemyLicenseRepository(uow)  # type: ignore[arg-type]
        use_case = ActivateLicenseUseCase(repository, token_hasher, status_checker, uow)
        license_ = await use_case.execute(
            ActivateLicenseCommand(tenant_id=target_tenant_id, presented_key=body.key)
        )
    return _license_response(license_)


@router.get(
    "/license", response_model=list[LicenseResponse], summary="List every tenant's license"
)
async def list_licenses(
    _principal: Annotated[
        PlatformPrincipal, Depends(require_live_platform_permission("license:manage_platform"))
    ],
    uow_factory: Annotated[_UowFactory, Depends(get_platform_unit_of_work_factory)],
) -> list[LicenseResponse]:
    async with uow_factory(None) as uow:
        license_repository = SqlAlchemyLicenseRepository(uow)  # type: ignore[arg-type]
        tenant_repository = SqlAlchemyTenantRepository(uow)  # type: ignore[arg-type]
        licenses = await ListLicensesUseCase(license_repository).execute(ListLicensesQuery())
        tenants = await ListTenantsUseCase(tenant_repository).execute(ListTenantsQuery())
        tenant_names = {tenant.id: tenant.name for tenant in tenants}
        return [
            _license_response(license_, tenant_name=tenant_names.get(license_.tenant_id))
            for license_ in licenses
        ]


@router.patch("/license/{tenant_id}/revoke", status_code=204, summary="Revoke a tenant's license")
async def revoke_license(
    tenant_id: str,
    _principal: Annotated[
        PlatformPrincipal, Depends(require_live_platform_permission("license:manage_platform"))
    ],
    uow_factory: Annotated[_UowFactory, Depends(get_platform_unit_of_work_factory)],
    status_checker: Annotated[LicenseStatusChecker, Depends(get_license_status_checker)],
) -> None:
    target_tenant_id = uuid.UUID(tenant_id)
    async with uow_factory(target_tenant_id) as uow:
        repository = SqlAlchemyLicenseRepository(uow)  # type: ignore[arg-type]
        use_case = RevokeLicenseUseCase(repository, status_checker, uow)
        await use_case.execute(RevokeLicenseCommand(tenant_id=target_tenant_id))


@router.patch(
    "/license/{tenant_id}/plan-tier", status_code=204, summary="Set a tenant's plan tier"
)
async def set_license_plan_tier(
    tenant_id: str,
    body: SetLicensePlanTierRequest,
    _principal: Annotated[
        PlatformPrincipal, Depends(require_live_platform_permission("license:manage_platform"))
    ],
    uow_factory: Annotated[_UowFactory, Depends(get_platform_unit_of_work_factory)],
) -> None:
    target_tenant_id = uuid.UUID(tenant_id)
    async with uow_factory(target_tenant_id) as uow:
        repository = SqlAlchemyLicenseRepository(uow)  # type: ignore[arg-type]
        use_case = SetLicensePlanTierUseCase(repository, uow)
        await use_case.execute(
            SetLicensePlanTierCommand(tenant_id=target_tenant_id, plan_tier=body.plan_tier)
        )


@router.patch(
    "/license/{tenant_id}/device-caps/{app_type}",
    status_code=204,
    summary="Set a tenant's per-app-type device cap",
)
async def set_license_device_cap(
    tenant_id: str,
    app_type: str,
    body: SetLicenseDeviceCapRequest,
    _principal: Annotated[
        PlatformPrincipal, Depends(require_live_platform_permission("license:manage_platform"))
    ],
    uow_factory: Annotated[_UowFactory, Depends(get_platform_unit_of_work_factory)],
) -> None:
    target_tenant_id = uuid.UUID(tenant_id)
    async with uow_factory(target_tenant_id) as uow:
        repository = SqlAlchemyLicenseRepository(uow)  # type: ignore[arg-type]
        use_case = SetLicenseDeviceCapUseCase(repository, uow)
        await use_case.execute(
            SetLicenseDeviceCapCommand(
                tenant_id=target_tenant_id, app_type=app_type, max_devices=body.max_devices
            )
        )


@router.put(
    "/license/{tenant_id}/feature-overrides/{key}",
    status_code=204,
    summary="Set a tenant's license feature override",
)
async def set_license_feature_override(
    tenant_id: str,
    key: str,
    body: SetLicenseFeatureOverrideRequest,
    _principal: Annotated[
        PlatformPrincipal, Depends(require_live_platform_permission("license:manage_platform"))
    ],
    uow_factory: Annotated[_UowFactory, Depends(get_platform_unit_of_work_factory)],
) -> None:
    target_tenant_id = uuid.UUID(tenant_id)
    async with uow_factory(target_tenant_id) as uow:
        override_repository = SqlAlchemyLicenseFeatureOverrideRepository(uow)  # type: ignore[arg-type]
        license_repository = SqlAlchemyLicenseRepository(uow)  # type: ignore[arg-type]
        use_case = SetLicenseFeatureOverrideUseCase(override_repository, license_repository, uow)
        await use_case.execute(
            SetLicenseFeatureOverrideCommand(
                tenant_id=target_tenant_id, feature_key=key, granted=body.granted
            )
        )


# -- Feature Flags (platform-tier — relocated from /admin/feature-flags) ------------


@router.get(
    "/feature-flags", response_model=list[FeatureFlagResponse], summary="List platform flags"
)
async def list_feature_flags(
    _principal: Annotated[
        PlatformPrincipal,
        Depends(require_live_platform_permission("feature_flags:manage_platform")),
    ],
    uow_factory: Annotated[_UowFactory, Depends(get_platform_unit_of_work_factory)],
) -> list[FeatureFlagResponse]:
    async with uow_factory(None) as uow:
        repository = SqlAlchemyFeatureFlagRepository(uow)  # type: ignore[arg-type]
        use_case = ListFeatureFlagsUseCase(repository)
        flags = await use_case.execute(ListFeatureFlagsQuery())
        return [
            FeatureFlagResponse(
                key=f.key,
                description=f.description,
                is_enabled_by_default=f.is_enabled_by_default,
                rollout_percentage=f.rollout_percentage,
                starts_at=f.starts_at,
                ends_at=f.ends_at,
            )
            for f in flags
        ]


@router.post(
    "/feature-flags",
    response_model=FeatureFlagResponse,
    status_code=201,
    summary="Create a platform flag",
)
async def create_feature_flag(
    body: CreateFeatureFlagRequest,
    _principal: Annotated[
        PlatformPrincipal,
        Depends(require_live_platform_permission("feature_flags:manage_platform")),
    ],
    uow_factory: Annotated[_UowFactory, Depends(get_platform_unit_of_work_factory)],
) -> FeatureFlagResponse:
    async with uow_factory(None) as uow:
        repository = SqlAlchemyFeatureFlagRepository(uow)  # type: ignore[arg-type]
        use_case = CreateFeatureFlagUseCase(repository, uow)
        flag = await use_case.execute(
            CreateFeatureFlagCommand(
                key=body.key,
                description=body.description,
                is_enabled_by_default=body.is_enabled_by_default,
                rollout_percentage=body.rollout_percentage,
            )
        )
    return FeatureFlagResponse(
        key=flag.key,
        description=flag.description,
        is_enabled_by_default=flag.is_enabled_by_default,
        rollout_percentage=flag.rollout_percentage,
        starts_at=flag.starts_at,
        ends_at=flag.ends_at,
    )


@router.patch(
    "/feature-flags/{key}/enabled-by-default",
    status_code=204,
    summary="Toggle a platform flag's default",
)
async def set_feature_flag_enabled_by_default(
    key: str,
    body: SetFeatureFlagEnabledByDefaultRequest,
    _principal: Annotated[
        PlatformPrincipal,
        Depends(require_live_platform_permission("feature_flags:manage_platform")),
    ],
    uow_factory: Annotated[_UowFactory, Depends(get_platform_unit_of_work_factory)],
) -> None:
    async with uow_factory(None) as uow:
        repository = SqlAlchemyFeatureFlagRepository(uow)  # type: ignore[arg-type]
        use_case = SetFeatureFlagEnabledByDefaultUseCase(repository, uow)
        await use_case.execute(
            SetFeatureFlagEnabledByDefaultCommand(key=key, enabled=body.enabled)
        )


@router.patch(
    "/feature-flags/{key}/rollout", status_code=204, summary="Set a platform flag's rollout %"
)
async def set_feature_flag_rollout_percentage(
    key: str,
    body: SetFeatureFlagRolloutPercentageRequest,
    _principal: Annotated[
        PlatformPrincipal,
        Depends(require_live_platform_permission("feature_flags:manage_platform")),
    ],
    uow_factory: Annotated[_UowFactory, Depends(get_platform_unit_of_work_factory)],
) -> None:
    async with uow_factory(None) as uow:
        repository = SqlAlchemyFeatureFlagRepository(uow)  # type: ignore[arg-type]
        use_case = SetFeatureFlagRolloutPercentageUseCase(repository, uow)
        await use_case.execute(
            SetFeatureFlagRolloutPercentageCommand(
                key=key, rollout_percentage=body.rollout_percentage
            )
        )


@router.patch("/feature-flags/{key}/schedule", status_code=204, summary="Schedule a platform flag")
async def schedule_feature_flag(
    key: str,
    body: ScheduleFeatureFlagRequest,
    _principal: Annotated[
        PlatformPrincipal,
        Depends(require_live_platform_permission("feature_flags:manage_platform")),
    ],
    uow_factory: Annotated[_UowFactory, Depends(get_platform_unit_of_work_factory)],
) -> None:
    async with uow_factory(None) as uow:
        repository = SqlAlchemyFeatureFlagRepository(uow)  # type: ignore[arg-type]
        use_case = ScheduleFeatureFlagUseCase(repository, uow)
        await use_case.execute(
            ScheduleFeatureFlagCommand(key=key, starts_at=body.starts_at, ends_at=body.ends_at)
        )


def _get_redis_cache() -> RedisCacheClient:
    from lpg.api.app import get_app_state

    state = get_app_state()
    if state.redis is None:
        msg = "RedisClient is not configured — the application lifespan has not run."
        raise RuntimeError(msg)
    return RedisCacheClient(state.redis)


def _get_database() -> Database:
    from lpg.api.app import get_app_state

    state = get_app_state()
    if state.database is None:
        msg = "Database is not connected — the application lifespan has not run."
        raise RuntimeError(msg)
    return state.database
