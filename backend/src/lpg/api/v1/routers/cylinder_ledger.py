import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from lpg.api.v1.dependencies.customer import get_customer_repository
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
from lpg.application.customer.ports import CustomerRepository
from lpg.application.cylinder_ledger.use_cases import (
    AdjustLedgerBalanceUseCase,
    GetCylinderLedgerUseCase,
)
from lpg.application.identity.ports import AuthenticatedPrincipal

router = APIRouter(prefix="/customers/{customer_id}/ledger", tags=["Cylinder Ledger"])


@router.get(
    "",
    response_model=CylinderLedgerResponse,
    dependencies=[Depends(require_permission("ledger:read"))],
)
async def get_ledger(
    customer_id: uuid.UUID,
    use_case: Annotated[
        GetCylinderLedgerUseCase, Depends(get_cylinder_ledger_use_case)
    ],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    customer_repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
) -> CylinderLedgerResponse:
    # `ledger:read` is held broadly (agency_admin/manager/accountant/customer)
    # -- a `customer` principal must additionally be scoped to their own
    # record, the same way `order.py`'s `_resolve_scope` forces `customer_id`
    # for order reads rather than trusting whatever the caller passed.
    # 404, not 403, on a mismatch — matches `_require_own_driver_order`'s
    # documented convention (OWASP API1: never let a caller distinguish
    # "not yours" from "doesn't exist").
    effective_customer_id = customer_id
    if principal.role == "customer":
        if principal.user_id is None:
            raise HTTPException(status_code=404, detail="Customer not found.")
        own_customer = await customer_repository.get_by_identity_user_id(principal.user_id)
        if own_customer is None or own_customer.id != customer_id:
            raise HTTPException(status_code=404, detail="Customer not found.")
        effective_customer_id = own_customer.id

    async with unit_of_work:
        ledger = await use_case.execute(
            tenant_id=principal.tenant_id,
            customer_id=effective_customer_id,
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
    use_case: Annotated[
        AdjustLedgerBalanceUseCase, Depends(get_adjust_ledger_balance_use_case)
    ],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> CylinderLedgerResponse:
    # A manual adjustment is always attributable to a real staff member --
    # a principal without a user_id (e.g. a machine token) cannot make one.
    if principal.user_id is None:
        raise HTTPException(status_code=401, detail="User ID is required.")

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
