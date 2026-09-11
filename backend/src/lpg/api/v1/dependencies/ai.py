"""FastAPI dependency providers for the AI Command Center (ADR-045)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from lpg.api.v1.dependencies.admin import get_tenant_configuration_repository
from lpg.api.v1.dependencies.complaint import get_complaint_unit_of_work
from lpg.api.v1.dependencies.identity import get_permission_checker
from lpg.api.v1.dependencies.inventory import get_inventory_location_repository
from lpg.api.v1.dependencies.order import get_order_repository
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.application.ai.ports import AssistantRunRepository, ModelGatewayPort
from lpg.application.ai.prediction import PredictionRepository
from lpg.application.ai.tools import ToolContext
from lpg.application.ai.use_cases import AskAiAssistantUseCase
from lpg.application.common.ports import UnitOfWork
from lpg.application.complaint.ports import ComplaintUnitOfWork
from lpg.application.identity.authorize import PermissionChecker
from lpg.application.inventory.ports import InventoryLocationRepository
from lpg.application.order.ports import OrderRepository
from lpg.application.tenant.ports import TenantConfigurationRepository
from lpg.config.settings import get_settings


def get_model_gateway() -> ModelGatewayPort:
    from lpg.infrastructure.ai.factory import get_model_gateway as build_gateway

    return build_gateway(get_settings())


def get_assistant_run_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> AssistantRunRepository:
    from lpg.infrastructure.persistence.repositories.ai import SqlAlchemyAssistantRunRepository

    return SqlAlchemyAssistantRunRepository(unit_of_work)  # type: ignore[arg-type]


def get_prediction_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> PredictionRepository:
    """`ai.prediction` reader — used by read endpoints that surface a
    heuristic's output (Stage 2's `GET /customers/refill-due`)."""
    from lpg.infrastructure.persistence.repositories.ai import SqlAlchemyPredictionRepository

    return SqlAlchemyPredictionRepository(unit_of_work)  # type: ignore[arg-type]


def get_tool_context(
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    inventory_repository: Annotated[
        InventoryLocationRepository, Depends(get_inventory_location_repository)
    ],
    complaint_uow: Annotated[ComplaintUnitOfWork, Depends(get_complaint_unit_of_work)],
) -> ToolContext:
    return ToolContext(
        order_repository=order_repository,
        inventory_repository=inventory_repository,
        complaint_uow=complaint_uow,
    )


def get_ask_ai_assistant_use_case(
    gateway: Annotated[ModelGatewayPort, Depends(get_model_gateway)],
    tenant_config_repository: Annotated[
        TenantConfigurationRepository, Depends(get_tenant_configuration_repository)
    ],
    assistant_run_repository: Annotated[
        AssistantRunRepository, Depends(get_assistant_run_repository)
    ],
    permission_checker: Annotated[PermissionChecker, Depends(get_permission_checker)],
    tool_context: Annotated[ToolContext, Depends(get_tool_context)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> AskAiAssistantUseCase:
    return AskAiAssistantUseCase(
        gateway=gateway,
        tenant_config_repository=tenant_config_repository,
        assistant_run_repository=assistant_run_repository,
        permission_checker=permission_checker,
        tool_context=tool_context,
        unit_of_work=unit_of_work,
    )
