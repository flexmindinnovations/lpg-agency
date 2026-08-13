from typing import Annotated
import uuid

from fastapi import APIRouter, Depends

from lpg.api.v1.dependencies.cylinder_ledger import (
    get_adjust_ledger_balance_use_case,
    get_cylinder_ledger_use_case,
)
from lpg.api.v1.dependencies.identity import get_current_principal, require_permission
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.api.v1.schemas.cylinder_ledger import (
    AdjustLedgerBalanceRequest,
    CylinderLedgerBalanceItem,
    CylinderLedgerResponse,
)
from lpg.application.common.ports import UnitOfWork
from lpg.application.cylinder_ledger.use_cases import (
    AdjustLedgerBalanceUseCase,
    GetCylinderLedgerUseCase,
)
from lpg.application.identity.ports import AuthenticatedPrincipal

router = APIRouter(prefix="/customers/{customer_id}/ledger", tags=["cylinder-ledger"])


@router.get(
    "",
    response_model=CylinderLedgerResponse,
    dependencies=[Depends(require_permission("customers:read"))],
)
async def get_ledger(
    customer_id: uuid.UUID,
    use_case: Annotated[GetCylinderLedgerUseCase, Depends(get_cylinder_ledger_use_case)],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> CylinderLedgerResponse:
    async with unit_of_work:
        ledger = await use_case.execute(
            tenant_id=principal.tenant_id,
            customer_id=customer_id,
        )
        return CylinderLedgerResponse(
            customer_id=ledger.customer_id,
            balances=[
                CylinderLedgerBalanceItem(cylinder_type_id=ct_id, quantity=q)
                for ct_id, q in ledger.balances.items()
            ],
        )


@router.post(
    "/adjust",
    response_model=CylinderLedgerResponse,
    dependencies=[Depends(require_permission("customers:update"))],
)
async def adjust_balance(
    customer_id: uuid.UUID,
    request: AdjustLedgerBalanceRequest,
    use_case: Annotated[AdjustLedgerBalanceUseCase, Depends(get_adjust_ledger_balance_use_case)],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> CylinderLedgerResponse:
    async with unit_of_work:
        ledger = await use_case.execute(
            tenant_id=principal.tenant_id,
            customer_id=customer_id,
            cylinder_type_id=request.cylinder_type_id,
            delta=request.delta,
            reason=request.reason,
            performed_by=principal.user_id,
        )
        await unit_of_work.commit()
        return CylinderLedgerResponse(
            customer_id=ledger.customer_id,
            balances=[
                CylinderLedgerBalanceItem(cylinder_type_id=ct_id, quantity=q)
                for ct_id, q in ledger.balances.items()
            ],
        )
