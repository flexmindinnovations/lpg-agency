"""API router for managing invoices."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from lpg.api.v1.dependencies.accounting import get_invoice_repository
from lpg.api.v1.dependencies.identity import require_permission
from lpg.api.v1.schemas.invoice import InvoicePageResponse, InvoiceResponse
from lpg.domain.accounting.invoice import Invoice
from lpg.application.accounting.ports import InvoiceRepository
from lpg.application.accounting.use_cases import (
    GetInvoiceQuery,
    GetInvoiceUseCase,
    ListInvoicesQuery,
    ListInvoicesUseCase,
)

router = APIRouter(prefix="/invoices", tags=["Invoices"])


def _invoice_to_response(invoice: Invoice) -> InvoiceResponse:
    # Since invoice_id vs id is a bit messy, let's use model_dump or construct it
    return InvoiceResponse.model_validate(invoice)


@router.get(
    "",
    response_model=InvoicePageResponse,
    dependencies=[Depends(require_permission("invoices:read"))],
)
async def list_invoices(
    repository: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    customer_id: uuid.UUID | None = None,
    order_id: uuid.UUID | None = None,
    status: str | None = None,
) -> InvoicePageResponse:
    """List invoices with optional filters."""
    use_case = ListInvoicesUseCase(repository)
    skip = (page - 1) * page_size
    items, total = await use_case.execute(
        ListInvoicesQuery(
            skip=skip,
            limit=page_size,
            customer_id=customer_id,
            order_id=order_id,
            status=status,
        )
    )

    return InvoicePageResponse(
        items=[_invoice_to_response(invoice) for invoice in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    dependencies=[Depends(require_permission("invoices:read"))],
)
async def get_invoice(
    invoice_id: uuid.UUID,
    repository: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
) -> InvoiceResponse:
    """Get a specific invoice by ID."""
    use_case = GetInvoiceUseCase(repository)
    invoice = await use_case.execute(GetInvoiceQuery(invoice_id=invoice_id))
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return _invoice_to_response(invoice)
