"""API router for driver cash handovers (R10, `CashShortfallDeclared`)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException

from lpg.api.v1.dependencies.accounting import (
    get_cash_handover_number_sequence,
    get_cash_handover_repository,
)
from lpg.api.v1.dependencies.delivery import get_driver_repository, get_route_repository
from lpg.api.v1.dependencies.identity import get_current_principal, require_permission
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.api.v1.schemas.cash_handover import (
    CashHandoverResponse,
    DeclareCashHandoverRequest,
    RouteCashHandoverResponse,
)
from lpg.application.accounting.ports import CashHandoverNumberSequence, CashHandoverRepository
from lpg.application.accounting.use_cases import (
    DeclareCashHandoverCommand,
    DeclareCashHandoverUseCase,
    GetRouteCashHandoverViewQuery,
    GetRouteCashHandoverViewUseCase,
)
from lpg.application.common.ports import UnitOfWork
from lpg.application.delivery.ports import DriverRepository, RouteRepository
from lpg.application.identity.ports import AuthenticatedPrincipal

if TYPE_CHECKING:
    from lpg.domain.accounting.cash_handover import CashHandover

router = APIRouter(prefix="/cash-handovers", tags=["Cash Handovers"])


def _to_response(handover: CashHandover) -> CashHandoverResponse:
    return CashHandoverResponse.model_validate(handover)


@router.get(
    "/for-route/{route_id}",
    response_model=RouteCashHandoverResponse,
    dependencies=[Depends(require_permission("cash_handovers:declare"))],
)
async def get_route_cash_handover(
    route_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    cash_handover_repository: Annotated[
        CashHandoverRepository, Depends(get_cash_handover_repository)
    ],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
) -> RouteCashHandoverResponse:
    """The Driver App's cash-handover screen: `expected_amount` (from the
    route's real cash proof-of-delivery records) plus the declared handover
    once it exists.

    A `driver` principal sees only their own routes; dispatch staff (who also
    hold `cash_handovers:declare`, per `c039189dfbdc`) can read any route in
    their tenant — same "or dispatcher/manager on their behalf" split as the
    declare endpoint. Either way `route_repository.get_by_id`'s RLS keeps it
    tenant-scoped, and a route the caller can't see is a `404`.
    """
    driver = (
        await driver_repository.get_by_identity_user_id(principal.user_id)
        if principal.user_id is not None
        else None
    )

    use_case = GetRouteCashHandoverViewUseCase(cash_handover_repository, route_repository)
    view = await use_case.execute(
        GetRouteCashHandoverViewQuery(
            route_id=route_id,
            driver_id=driver.id if driver is not None else None,
        )
    )
    return RouteCashHandoverResponse.model_validate(view)


@router.post(
    "",
    response_model=CashHandoverResponse,
    status_code=201,
    dependencies=[Depends(require_permission("cash_handovers:declare"))],
)
async def declare_cash_handover(
    request: DeclareCashHandoverRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    cash_handover_repository: Annotated[
        CashHandoverRepository, Depends(get_cash_handover_repository)
    ],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    handover_number_sequence: Annotated[
        CashHandoverNumberSequence, Depends(get_cash_handover_number_sequence)
    ],
) -> CashHandoverResponse:
    """A driver (or dispatcher/manager on their behalf) declares the cash
    handed over at the end of a route. `expected_amount` is computed
    server-side from real cash-payment proof-of-delivery records — never
    trusted from the request.
    """
    if principal.user_id is None:
        raise HTTPException(status_code=401, detail="User ID is required.")
    use_case = DeclareCashHandoverUseCase(
        cash_handover_repository, route_repository, unit_of_work, handover_number_sequence
    )
    handover = await use_case.execute(
        DeclareCashHandoverCommand(
            driver_id=request.driver_id,
            route_id=request.route_id,
            actual_amount=request.actual_amount,
            declared_by=principal.user_id,
        )
    )
    return _to_response(handover)
