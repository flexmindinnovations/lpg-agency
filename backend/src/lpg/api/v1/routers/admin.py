"""Administration endpoints (Phase 7) — tenant/branch/warehouse/cylinder-type/
tenant-configuration/price-list/feature-flags/staff-users/audit-log.

Mounted under `/admin`. Gated by `require_permission("tenant:configure")`
for master-data CRUD, `require_permission("users:manage")` for staff
management, `require_permission("feature_flags:manage_tenant")` for tenant
flag overrides, `require_live_permission("feature_flags:manage_platform")`
for platform flag management (super_admin only, live-checked — same
high-sensitivity pattern `reconciliation:approve` uses), and
`require_permission("audit:read")` for the audit log.

**Every type used inside `Annotated[X, Depends(...)]` below is a real
import, never `TYPE_CHECKING`-guarded** — see `api/v1/routers/auth.py`'s
module docstring for the FastAPI footgun this avoids.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends

from lpg.api.v1.dependencies.admin import (
    get_audit_log_repository,
    get_branch_repository,
    get_cylinder_type_repository,
    get_feature_flag_override_repository,
    get_feature_flag_repository,
    get_price_list_repository,
    get_staff_user_repository,
    get_tenant_configuration_repository,
    get_tenant_repository,
    get_warehouse_repository,
)
from lpg.api.v1.dependencies.identity import (
    get_current_principal,
    get_email_sender,
    get_password_reset_token_repository,
    get_permission_repository,
    get_refresh_token_repository,
    get_token_hasher,
    require_live_permission,
    require_permission,
)
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.api.v1.schemas.admin import (
    AdjustCylinderTypeWeightRequest,
    AuditLogEntryResponse,
    AuditLogPageResponse,
    BranchResponse,
    CreateBranchRequest,
    CreateCylinderTypeRequest,
    CreateFeatureFlagRequest,
    CreateWarehouseRequest,
    CylinderTypeResponse,
    FeatureFlagEnabledResponse,
    FeatureFlagOverrideResponse,
    FeatureFlagResponse,
    InviteStaffUserRequest,
    PriceListEntryResponse,
    ReassignRoleRequest,
    RelocateWarehouseRequest,
    RenameBranchRequest,
    RenameCylinderTypeRequest,
    RenameTenantRequest,
    RenameWarehouseRequest,
    ScheduleFeatureFlagRequest,
    SetBranchRegionRequest,
    SetCylinderTypeActiveRequest,
    SetFeatureFlagEnabledByDefaultRequest,
    SetFeatureFlagOverrideRequest,
    SetFeatureFlagRolloutPercentageRequest,
    SetPriceRequest,
    SetTenantConfigurationRequest,
    StaffUserResponse,
    TenantConfigurationResponse,
    TenantResponse,
    UpdateStaffUserPermissionsRequest,
    WarehouseResponse,
)
from lpg.application.audit.list_audit_log import ListAuditLogQuery, ListAuditLogUseCase
from lpg.application.audit.ports import AuditLogRepository
from lpg.application.common.errors import NotFoundError
from lpg.application.common.ports import UnitOfWork
from lpg.application.identity.ports import (
    AuthenticatedPrincipal,
    EmailSender,
    PasswordResetTokenRepository,
    PermissionRepository,
    RefreshTokenRepository,
    StaffUserRepository,
    TokenHasher,
)
from lpg.application.identity.staff_user import (
    DeactivateStaffUserCommand,
    DeactivateStaffUserUseCase,
    GetStaffUserPermissionsQuery,
    GetStaffUserPermissionsUseCase,
    InviteStaffUserCommand,
    InviteStaffUserUseCase,
    ListPermissionsQuery,
    ListPermissionsUseCase,
    ListStaffUsersQuery,
    ListStaffUsersUseCase,
    ReassignRoleCommand,
    ReassignRoleUseCase,
    UpdateStaffUserPermissionsCommand,
    UpdateStaffUserPermissionsUseCase,
)
from lpg.application.platform.feature_flag import (
    CreateFeatureFlagCommand,
    CreateFeatureFlagUseCase,
    IsFeatureFlagEnabledQuery,
    IsFeatureFlagEnabledUseCase,
    ListFeatureFlagsQuery,
    ListFeatureFlagsUseCase,
    ScheduleFeatureFlagCommand,
    ScheduleFeatureFlagUseCase,
    SetFeatureFlagEnabledByDefaultCommand,
    SetFeatureFlagEnabledByDefaultUseCase,
    SetFeatureFlagRolloutPercentageCommand,
    SetFeatureFlagRolloutPercentageUseCase,
    SetTenantFeatureFlagOverrideCommand,
    SetTenantFeatureFlagOverrideUseCase,
)
from lpg.application.platform.ports import FeatureFlagOverrideRepository, FeatureFlagRepository
from lpg.application.tenant.branch import (
    CreateBranchCommand,
    CreateBranchUseCase,
    ListBranchesQuery,
    ListBranchesUseCase,
    RenameBranchCommand,
    RenameBranchUseCase,
    SetBranchRegionCommand,
    SetBranchRegionUseCase,
)
from lpg.application.tenant.cylinder_type import (
    AdjustCylinderTypeWeightCommand,
    AdjustCylinderTypeWeightUseCase,
    CreateCylinderTypeCommand,
    CreateCylinderTypeUseCase,
    ListCylinderTypesQuery,
    ListCylinderTypesUseCase,
    RenameCylinderTypeCommand,
    RenameCylinderTypeUseCase,
    SetCylinderTypeActiveCommand,
    SetCylinderTypeActiveUseCase,
)
from lpg.application.tenant.ports import (
    BranchRepository,
    CylinderTypeRepository,
    PriceListRepository,
    TenantConfigurationRepository,
    TenantRepository,
    WarehouseRepository,
)
from lpg.application.tenant.price_list import (
    GetEffectivePriceQuery,
    GetEffectivePriceUseCase,
    ListPricesQuery,
    ListPricesUseCase,
    SetPriceCommand,
    SetPriceUseCase,
)
from lpg.application.tenant.rename_tenant import RenameTenantCommand, RenameTenantUseCase
from lpg.application.tenant.tenant_configuration import (
    GetEffectiveTenantConfigurationQuery,
    GetEffectiveTenantConfigurationUseCase,
    ListTenantConfigurationQuery,
    ListTenantConfigurationUseCase,
    SetTenantConfigurationCommand,
    SetTenantConfigurationUseCase,
)
from lpg.application.tenant.warehouse import (
    CreateWarehouseCommand,
    CreateWarehouseUseCase,
    ListWarehousesQuery,
    ListWarehousesUseCase,
    RelocateWarehouseCommand,
    RelocateWarehouseUseCase,
    RenameWarehouseCommand,
    RenameWarehouseUseCase,
)
from lpg.config.settings import Settings, get_settings

router = APIRouter(prefix="/admin", tags=["Administration"])


# -- Tenant -------------------------------------------------------------------


@router.get("/tenant", response_model=TenantResponse, summary="The current tenant")
async def get_tenant(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("tenant:read"))],
    repository: Annotated[TenantRepository, Depends(get_tenant_repository)],
) -> TenantResponse:
    tenant = await repository.get(principal.tenant_id)
    if tenant is None:
        msg = f"No tenant visible with id {principal.tenant_id}."
        raise NotFoundError(msg, tenant_id=str(principal.tenant_id))
    return TenantResponse(
        id=str(tenant.id),
        name=tenant.name,
        slug=tenant.slug,
        status=tenant.status,
        subscription_plan=tenant.subscription_plan,
        primary_contact_email=tenant.primary_contact_email,
        country=tenant.country,
    )


@router.patch("/tenant/rename", response_model=TenantResponse, summary="Rename the current tenant")
async def rename_tenant(
    body: RenameTenantRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("tenant:configure"))],
    repository: Annotated[TenantRepository, Depends(get_tenant_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> TenantResponse:
    use_case = RenameTenantUseCase(repository, unit_of_work)
    await use_case.execute(RenameTenantCommand(tenant_id=principal.tenant_id, new_name=body.name))
    tenant = await repository.get(principal.tenant_id)
    assert tenant is not None
    return TenantResponse(
        id=str(tenant.id),
        name=tenant.name,
        slug=tenant.slug,
        status=tenant.status,
        subscription_plan=tenant.subscription_plan,
        primary_contact_email=tenant.primary_contact_email,
        country=tenant.country,
    )


# -- Branches -------------------------------------------------------------------


@router.get("/branches", response_model=list[BranchResponse], summary="List branches")
async def list_branches(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[BranchRepository, Depends(get_branch_repository)],
) -> list[BranchResponse]:
    use_case = ListBranchesUseCase(repository)
    branches = await use_case.execute(ListBranchesQuery(tenant_id=principal.tenant_id))
    return [BranchResponse(id=str(b.id), name=b.name, region=b.region) for b in branches]


@router.post("/branches", response_model=BranchResponse, status_code=201, summary="Create a branch")
async def create_branch(
    body: CreateBranchRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("tenant:configure"))],
    repository: Annotated[BranchRepository, Depends(get_branch_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> BranchResponse:
    use_case = CreateBranchUseCase(repository, unit_of_work)
    branch = await use_case.execute(
        CreateBranchCommand(tenant_id=principal.tenant_id, name=body.name, region=body.region)
    )
    return BranchResponse(id=str(branch.id), name=branch.name, region=branch.region)


@router.patch("/branches/{branch_id}/rename", status_code=204, summary="Rename a branch")
async def rename_branch(
    branch_id: uuid.UUID,
    body: RenameBranchRequest,
    _principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("tenant:configure"))],
    repository: Annotated[BranchRepository, Depends(get_branch_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    use_case = RenameBranchUseCase(repository, unit_of_work)
    await use_case.execute(RenameBranchCommand(branch_id=branch_id, new_name=body.name))


@router.patch("/branches/{branch_id}/region", status_code=204, summary="Set a branch's region")
async def set_branch_region(
    branch_id: uuid.UUID,
    body: SetBranchRegionRequest,
    _principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("tenant:configure"))],
    repository: Annotated[BranchRepository, Depends(get_branch_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    use_case = SetBranchRegionUseCase(repository, unit_of_work)
    await use_case.execute(SetBranchRegionCommand(branch_id=branch_id, region=body.region))


# -- Warehouses -----------------------------------------------------------------


@router.get("/warehouses", response_model=list[WarehouseResponse], summary="List warehouses")
async def list_warehouses(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[WarehouseRepository, Depends(get_warehouse_repository)],
) -> list[WarehouseResponse]:
    use_case = ListWarehousesUseCase(repository)
    warehouses = await use_case.execute(ListWarehousesQuery(tenant_id=principal.tenant_id))
    return [
        WarehouseResponse(
            id=str(w.id), branch_id=str(w.branch_id), name=w.name, address_line=w.address_line
        )
        for w in warehouses
    ]


@router.post(
    "/warehouses", response_model=WarehouseResponse, status_code=201, summary="Create a warehouse"
)
async def create_warehouse(
    body: CreateWarehouseRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("tenant:configure"))],
    repository: Annotated[WarehouseRepository, Depends(get_warehouse_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> WarehouseResponse:
    use_case = CreateWarehouseUseCase(repository, unit_of_work)
    warehouse = await use_case.execute(
        CreateWarehouseCommand(
            tenant_id=principal.tenant_id,
            branch_id=uuid.UUID(body.branch_id),
            name=body.name,
            address_line=body.address_line,
        )
    )
    return WarehouseResponse(
        id=str(warehouse.id),
        branch_id=str(warehouse.branch_id),
        name=warehouse.name,
        address_line=warehouse.address_line,
    )


@router.patch("/warehouses/{warehouse_id}/rename", status_code=204, summary="Rename a warehouse")
async def rename_warehouse(
    warehouse_id: uuid.UUID,
    body: RenameWarehouseRequest,
    _principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("tenant:configure"))],
    repository: Annotated[WarehouseRepository, Depends(get_warehouse_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    use_case = RenameWarehouseUseCase(repository, unit_of_work)
    await use_case.execute(RenameWarehouseCommand(warehouse_id=warehouse_id, new_name=body.name))


@router.patch(
    "/warehouses/{warehouse_id}/relocate", status_code=204, summary="Relocate a warehouse"
)
async def relocate_warehouse(
    warehouse_id: uuid.UUID,
    body: RelocateWarehouseRequest,
    _principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("tenant:configure"))],
    repository: Annotated[WarehouseRepository, Depends(get_warehouse_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    use_case = RelocateWarehouseUseCase(repository, unit_of_work)
    await use_case.execute(
        RelocateWarehouseCommand(warehouse_id=warehouse_id, new_address_line=body.address_line)
    )


# -- Cylinder Types -------------------------------------------------------------


@router.get(
    "/cylinder-types", response_model=list[CylinderTypeResponse], summary="List cylinder types"
)
async def list_cylinder_types(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[CylinderTypeRepository, Depends(get_cylinder_type_repository)],
) -> list[CylinderTypeResponse]:
    use_case = ListCylinderTypesUseCase(repository)
    cylinder_types = await use_case.execute(ListCylinderTypesQuery(tenant_id=principal.tenant_id))
    return [
        CylinderTypeResponse(
            id=str(c.id), name=c.name, weight_kg=c.weight_kg, is_active=c.is_active
        )
        for c in cylinder_types
    ]


@router.post(
    "/cylinder-types",
    response_model=CylinderTypeResponse,
    status_code=201,
    summary="Create a cylinder type",
)
async def create_cylinder_type(
    body: CreateCylinderTypeRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("tenant:configure"))],
    repository: Annotated[CylinderTypeRepository, Depends(get_cylinder_type_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> CylinderTypeResponse:
    use_case = CreateCylinderTypeUseCase(repository, unit_of_work)
    cylinder_type = await use_case.execute(
        CreateCylinderTypeCommand(
            tenant_id=principal.tenant_id, name=body.name, weight_kg=body.weight_kg
        )
    )
    return CylinderTypeResponse(
        id=str(cylinder_type.id),
        name=cylinder_type.name,
        weight_kg=cylinder_type.weight_kg,
        is_active=cylinder_type.is_active,
    )


@router.patch(
    "/cylinder-types/{cylinder_type_id}/rename", status_code=204, summary="Rename a cylinder type"
)
async def rename_cylinder_type(
    cylinder_type_id: uuid.UUID,
    body: RenameCylinderTypeRequest,
    _principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("tenant:configure"))],
    repository: Annotated[CylinderTypeRepository, Depends(get_cylinder_type_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    use_case = RenameCylinderTypeUseCase(repository, unit_of_work)
    await use_case.execute(
        RenameCylinderTypeCommand(cylinder_type_id=cylinder_type_id, new_name=body.name)
    )


@router.patch(
    "/cylinder-types/{cylinder_type_id}/weight",
    status_code=204,
    summary="Adjust a cylinder type's weight",
)
async def adjust_cylinder_type_weight(
    cylinder_type_id: uuid.UUID,
    body: AdjustCylinderTypeWeightRequest,
    _principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("tenant:configure"))],
    repository: Annotated[CylinderTypeRepository, Depends(get_cylinder_type_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    use_case = AdjustCylinderTypeWeightUseCase(repository, unit_of_work)
    await use_case.execute(
        AdjustCylinderTypeWeightCommand(
            cylinder_type_id=cylinder_type_id, new_weight_kg=body.weight_kg
        )
    )


@router.patch(
    "/cylinder-types/{cylinder_type_id}/active",
    status_code=204,
    summary="Activate or deactivate a cylinder type",
)
async def set_cylinder_type_active(
    cylinder_type_id: uuid.UUID,
    body: SetCylinderTypeActiveRequest,
    _principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("tenant:configure"))],
    repository: Annotated[CylinderTypeRepository, Depends(get_cylinder_type_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    use_case = SetCylinderTypeActiveUseCase(repository, unit_of_work)
    await use_case.execute(
        SetCylinderTypeActiveCommand(cylinder_type_id=cylinder_type_id, is_active=body.is_active)
    )


# -- Tenant Configuration ---------------------------------------------------------


@router.get(
    "/tenant-configuration",
    response_model=list[TenantConfigurationResponse],
    summary="List tenant configuration history",
)
async def list_tenant_configuration(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("tenant:configure"))],
    repository: Annotated[
        TenantConfigurationRepository, Depends(get_tenant_configuration_repository)
    ],
) -> list[TenantConfigurationResponse]:
    use_case = ListTenantConfigurationUseCase(repository)
    entries = await use_case.execute(ListTenantConfigurationQuery(tenant_id=principal.tenant_id))
    return [
        TenantConfigurationResponse(
            id=str(e.id),
            config_key=e.config_key,
            config_value=e.config_value,
            effective_from=e.effective_from,
        )
        for e in entries
    ]


@router.post(
    "/tenant-configuration",
    response_model=TenantConfigurationResponse,
    status_code=201,
    summary="Set a tenant configuration value",
)
async def set_tenant_configuration(
    body: SetTenantConfigurationRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("tenant:configure"))],
    repository: Annotated[
        TenantConfigurationRepository, Depends(get_tenant_configuration_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> TenantConfigurationResponse:
    use_case = SetTenantConfigurationUseCase(repository, unit_of_work)
    entry = await use_case.execute(
        SetTenantConfigurationCommand(
            tenant_id=principal.tenant_id,
            config_key=body.config_key,
            config_value=body.config_value,
            effective_from=body.effective_from,
        )
    )
    return TenantConfigurationResponse(
        id=str(entry.id),
        config_key=entry.config_key,
        config_value=entry.config_value,
        effective_from=entry.effective_from,
    )


@router.get(
    "/tenant-configuration/effective",
    response_model=TenantConfigurationResponse | None,
    summary="The effective value for a config key",
)
async def get_effective_tenant_configuration(
    config_key: str,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("tenant:configure"))],
    repository: Annotated[
        TenantConfigurationRepository, Depends(get_tenant_configuration_repository)
    ],
) -> TenantConfigurationResponse | None:
    use_case = GetEffectiveTenantConfigurationUseCase(repository)
    entry = await use_case.execute(
        GetEffectiveTenantConfigurationQuery(tenant_id=principal.tenant_id, config_key=config_key)
    )
    if entry is None:
        return None
    return TenantConfigurationResponse(
        id=str(entry.id),
        config_key=entry.config_key,
        config_value=entry.config_value,
        effective_from=entry.effective_from,
    )


# -- Price List -----------------------------------------------------------------


@router.get("/price-list", response_model=list[PriceListEntryResponse], summary="List prices")
async def list_prices(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[PriceListRepository, Depends(get_price_list_repository)],
) -> list[PriceListEntryResponse]:
    use_case = ListPricesUseCase(repository)
    entries = await use_case.execute(ListPricesQuery(tenant_id=principal.tenant_id))
    return [
        PriceListEntryResponse(
            id=str(e.id),
            cylinder_type_id=str(e.cylinder_type_id),
            customer_type=e.customer_type,
            branch_id=str(e.branch_id) if e.branch_id else None,
            price=e.price,
            effective_from=e.effective_from,
        )
        for e in entries
    ]


@router.post(
    "/price-list", response_model=PriceListEntryResponse, status_code=201, summary="Set a price"
)
async def set_price(
    body: SetPriceRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("tenant:configure"))],
    repository: Annotated[PriceListRepository, Depends(get_price_list_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> PriceListEntryResponse:
    use_case = SetPriceUseCase(repository, unit_of_work)
    entry = await use_case.execute(
        SetPriceCommand(
            tenant_id=principal.tenant_id,
            cylinder_type_id=uuid.UUID(body.cylinder_type_id),
            customer_type=body.customer_type,
            price=body.price,
            branch_id=uuid.UUID(body.branch_id) if body.branch_id else None,
            effective_from=body.effective_from,
        )
    )
    return PriceListEntryResponse(
        id=str(entry.id),
        cylinder_type_id=str(entry.cylinder_type_id),
        customer_type=entry.customer_type,
        branch_id=str(entry.branch_id) if entry.branch_id else None,
        price=entry.price,
        effective_from=entry.effective_from,
    )


@router.get(
    "/price-list/effective",
    response_model=PriceListEntryResponse | None,
    summary="The effective price for a cylinder type x customer type",
)
async def get_effective_price(
    cylinder_type_id: uuid.UUID,
    customer_type: str,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[PriceListRepository, Depends(get_price_list_repository)],
    branch_id: uuid.UUID | None = None,
) -> PriceListEntryResponse | None:
    use_case = GetEffectivePriceUseCase(repository)
    entry = await use_case.execute(
        GetEffectivePriceQuery(
            tenant_id=principal.tenant_id,
            cylinder_type_id=cylinder_type_id,
            customer_type=customer_type,
            branch_id=branch_id,
        )
    )
    if entry is None:
        return None
    return PriceListEntryResponse(
        id=str(entry.id),
        cylinder_type_id=str(entry.cylinder_type_id),
        customer_type=entry.customer_type,
        branch_id=str(entry.branch_id) if entry.branch_id else None,
        price=entry.price,
        effective_from=entry.effective_from,
    )


# -- Feature Flags (platform) -----------------------------------------------------


@router.get(
    "/feature-flags", response_model=list[FeatureFlagResponse], summary="List platform flags"
)
async def list_feature_flags(
    _principal: Annotated[
        AuthenticatedPrincipal, Depends(require_live_permission("feature_flags:manage_platform"))
    ],
    repository: Annotated[FeatureFlagRepository, Depends(get_feature_flag_repository)],
) -> list[FeatureFlagResponse]:
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
        AuthenticatedPrincipal, Depends(require_live_permission("feature_flags:manage_platform"))
    ],
    repository: Annotated[FeatureFlagRepository, Depends(get_feature_flag_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> FeatureFlagResponse:
    use_case = CreateFeatureFlagUseCase(repository, unit_of_work)
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
        AuthenticatedPrincipal, Depends(require_live_permission("feature_flags:manage_platform"))
    ],
    repository: Annotated[FeatureFlagRepository, Depends(get_feature_flag_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    use_case = SetFeatureFlagEnabledByDefaultUseCase(repository, unit_of_work)
    await use_case.execute(SetFeatureFlagEnabledByDefaultCommand(key=key, enabled=body.enabled))


@router.patch(
    "/feature-flags/{key}/rollout", status_code=204, summary="Set a platform flag's rollout %"
)
async def set_feature_flag_rollout_percentage(
    key: str,
    body: SetFeatureFlagRolloutPercentageRequest,
    _principal: Annotated[
        AuthenticatedPrincipal, Depends(require_live_permission("feature_flags:manage_platform"))
    ],
    repository: Annotated[FeatureFlagRepository, Depends(get_feature_flag_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    use_case = SetFeatureFlagRolloutPercentageUseCase(repository, unit_of_work)
    await use_case.execute(
        SetFeatureFlagRolloutPercentageCommand(key=key, rollout_percentage=body.rollout_percentage)
    )


@router.patch("/feature-flags/{key}/schedule", status_code=204, summary="Schedule a platform flag")
async def schedule_feature_flag(
    key: str,
    body: ScheduleFeatureFlagRequest,
    _principal: Annotated[
        AuthenticatedPrincipal, Depends(require_live_permission("feature_flags:manage_platform"))
    ],
    repository: Annotated[FeatureFlagRepository, Depends(get_feature_flag_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    use_case = ScheduleFeatureFlagUseCase(repository, unit_of_work)
    await use_case.execute(
        ScheduleFeatureFlagCommand(key=key, starts_at=body.starts_at, ends_at=body.ends_at)
    )


@router.get(
    "/feature-flags/{key}/enabled",
    response_model=FeatureFlagEnabledResponse,
    summary="Whether a flag is enabled for the current tenant",
)
async def is_feature_flag_enabled(
    key: str,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    flag_repository: Annotated[FeatureFlagRepository, Depends(get_feature_flag_repository)],
    override_repository: Annotated[
        FeatureFlagOverrideRepository, Depends(get_feature_flag_override_repository)
    ],
) -> FeatureFlagEnabledResponse:
    """No special permission beyond authentication — any authenticated
    principal's client may need to know whether a flag is on for its own
    tenant, unlike managing the flag itself.
    """
    use_case = IsFeatureFlagEnabledUseCase(flag_repository, override_repository)
    enabled = await use_case.execute(
        IsFeatureFlagEnabledQuery(tenant_id=principal.tenant_id, flag_key=key)
    )
    return FeatureFlagEnabledResponse(key=key, enabled=enabled)


# -- Feature Flags (tenant overrides) ----------------------------------------------


@router.put(
    "/feature-flags/overrides/{key}",
    response_model=FeatureFlagOverrideResponse,
    summary="Set this tenant's override for a flag",
)
async def set_feature_flag_override(
    key: str,
    body: SetFeatureFlagOverrideRequest,
    principal: Annotated[
        AuthenticatedPrincipal, Depends(require_permission("feature_flags:manage_tenant"))
    ],
    override_repository: Annotated[
        FeatureFlagOverrideRepository, Depends(get_feature_flag_override_repository)
    ],
    flag_repository: Annotated[FeatureFlagRepository, Depends(get_feature_flag_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> FeatureFlagOverrideResponse:
    use_case = SetTenantFeatureFlagOverrideUseCase(
        override_repository, flag_repository, unit_of_work
    )
    await use_case.execute(
        SetTenantFeatureFlagOverrideCommand(
            tenant_id=principal.tenant_id, flag_key=key, enabled=body.enabled
        )
    )
    return FeatureFlagOverrideResponse(flag_key=key, is_enabled=body.enabled)


# -- Staff Users ------------------------------------------------------------------


@router.get("/users", response_model=list[StaffUserResponse], summary="List staff users")
async def list_staff_users(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("users:manage"))],
    repository: Annotated[StaffUserRepository, Depends(get_staff_user_repository)],
) -> list[StaffUserResponse]:
    use_case = ListStaffUsersUseCase(repository)
    users = await use_case.execute(ListStaffUsersQuery(tenant_id=principal.tenant_id))
    return [
        StaffUserResponse(
            id=str(u.id),
            email=u.email,
            role=u.role,
            branch_id=str(u.branch_id) if u.branch_id else None,
            is_active=u.is_active,
        )
        for u in users
    ]


@router.post(
    "/users", response_model=StaffUserResponse, status_code=201, summary="Invite a staff user"
)
async def invite_staff_user(
    body: InviteStaffUserRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("users:manage"))],
    repository: Annotated[StaffUserRepository, Depends(get_staff_user_repository)],
    reset_token_repository: Annotated[
        PasswordResetTokenRepository, Depends(get_password_reset_token_repository)
    ],
    token_hasher: Annotated[TokenHasher, Depends(get_token_hasher)],
    email_sender: Annotated[EmailSender, Depends(get_email_sender)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StaffUserResponse:
    use_case = InviteStaffUserUseCase(
        repository,
        reset_token_repository,
        token_hasher,
        email_sender,
        reset_token_ttl=timedelta(seconds=settings.password_reset_token_ttl_seconds),
    )
    user = await use_case.execute(
        InviteStaffUserCommand(
            tenant_id=principal.tenant_id,
            email=body.email,
            role=body.role,
            branch_id=uuid.UUID(body.branch_id) if body.branch_id else None,
        )
    )
    return StaffUserResponse(
        id=str(user.id),
        email=user.email,
        role=user.role,
        branch_id=str(user.branch_id) if user.branch_id else None,
        is_active=user.is_active,
    )


@router.patch("/users/{user_id}/deactivate", status_code=204, summary="Deactivate a staff user")
async def deactivate_staff_user(
    user_id: uuid.UUID,
    _principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("users:manage"))],
    repository: Annotated[StaffUserRepository, Depends(get_staff_user_repository)],
    refresh_token_repository: Annotated[
        RefreshTokenRepository, Depends(get_refresh_token_repository)
    ],
) -> None:
    use_case = DeactivateStaffUserUseCase(repository, refresh_token_repository)
    await use_case.execute(DeactivateStaffUserCommand(user_id=user_id))


@router.patch("/users/{user_id}/role", status_code=204, summary="Reassign a staff user's role")
async def reassign_role(
    user_id: uuid.UUID,
    body: ReassignRoleRequest,
    _principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("users:manage"))],
    repository: Annotated[StaffUserRepository, Depends(get_staff_user_repository)],
) -> None:
    use_case = ReassignRoleUseCase(repository)
    await use_case.execute(ReassignRoleCommand(user_id=user_id, new_role=body.new_role))


@router.get(
    "/users/{user_id}/permissions",
    response_model=list[str],
    summary="Get a staff user's permissions",
)
async def get_user_permissions(
    user_id: uuid.UUID,
    _principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("users:manage"))],
    staff_repository: Annotated[StaffUserRepository, Depends(get_staff_user_repository)],
    permission_repository: Annotated[PermissionRepository, Depends(get_permission_repository)],
) -> list[str]:
    use_case = GetStaffUserPermissionsUseCase(staff_repository, permission_repository)
    codes = await use_case.execute(GetStaffUserPermissionsQuery(user_id=user_id))
    return sorted(list(codes))


@router.put(
    "/users/{user_id}/permissions",
    status_code=204,
    summary="Update a staff user's permissions",
)
async def update_user_permissions(
    user_id: uuid.UUID,
    body: UpdateStaffUserPermissionsRequest,
    _principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("users:manage"))],
    staff_repository: Annotated[StaffUserRepository, Depends(get_staff_user_repository)],
    permission_repository: Annotated[PermissionRepository, Depends(get_permission_repository)],
) -> None:
    use_case = UpdateStaffUserPermissionsUseCase(staff_repository, permission_repository)
    await use_case.execute(
        UpdateStaffUserPermissionsCommand(
            user_id=user_id, permission_codes=set(body.permission_codes)
        )
    )

@router.get(
    "/permissions",
    response_model=list[str],
    summary="List all available system permissions",
)
async def list_permissions(
    _principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("users:manage"))],
    permission_repository: Annotated[PermissionRepository, Depends(get_permission_repository)],
) -> list[str]:
    use_case = ListPermissionsUseCase(permission_repository)
    codes = await use_case.execute(ListPermissionsQuery())
    return sorted(list(codes))



# -- Audit Log ----------------------------------------------------------------------


@router.get("/audit-log", response_model=AuditLogPageResponse, summary="View the audit log")
async def list_audit_log(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("audit:read"))],
    repository: Annotated[AuditLogRepository, Depends(get_audit_log_repository)],
    entity_name: str | None = None,
    actor_id: uuid.UUID | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> AuditLogPageResponse:
    use_case = ListAuditLogUseCase(repository)
    page = await use_case.execute(
        ListAuditLogQuery(
            tenant_id=principal.tenant_id,
            entity_name=entity_name,
            actor_id=actor_id,
            cursor=cursor,
            limit=limit,
        )
    )
    return AuditLogPageResponse(
        items=[
            AuditLogEntryResponse(
                id=str(entry.id),
                actor_id=str(entry.actor_id) if entry.actor_id else None,
                actor_display_name=entry.actor_display_name,
                entity_name=entry.entity_name,
                entity_id=entry.entity_id,
                entity_display_name=entry.entity_display_name,
                action=entry.action,
                performed_at=entry.performed_at,
                correlation_id=entry.correlation_id,
                before_state=entry.before_state,
                after_state=entry.after_state,
            )
            for entry in page.items
        ],
        next_cursor=page.next_cursor,
    )
