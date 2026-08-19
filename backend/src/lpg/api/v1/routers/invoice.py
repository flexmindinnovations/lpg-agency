"""API router for managing invoices."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from lpg.api.v1.dependencies.accounting import get_invoice_repository
from lpg.api.v1.dependencies.identity import require_permission
from lpg.api.v1.schemas.invoice import InvoiceLineResponse, InvoicePageResponse, InvoiceResponse
from lpg.application.accounting.ports import InvoiceRepository
from lpg.application.accounting.use_cases import (
    GetInvoiceQuery,
    GetInvoiceUseCase,
    ListInvoicesQuery,
    ListInvoicesUseCase,
)
from lpg.domain.accounting.invoice import Invoice

router = APIRouter(prefix="/invoices", tags=["Invoices"])


def _invoice_to_response(invoice: Invoice) -> InvoiceResponse:
    # `Invoice`/`InvoiceLine` only expose `.id` (from `Entity`), while the
    # committed schema names these fields `invoice_id`/`line_id` — the
    # frontend's generated client and `feature-invoices.ts` already depend on
    # that naming, so the fix is here, not a schema rename. Built field-by-
    # field, matching `_order_to_response`'s convention, rather than
    # `InvoiceResponse.model_validate(invoice)`, which fails validation on
    # every real invoice since neither attribute name exists on the domain
    # object.
    return InvoiceResponse(
        invoice_id=invoice.id,
        tenant_id=invoice.tenant_id,
        customer_id=invoice.customer_id,
        order_id=invoice.order_id,
        status=invoice.status,
        issued_at=invoice.issued_at,
        lines=[
            InvoiceLineResponse(
                line_id=line.id,
                cylinder_type_id=line.cylinder_type_id,
                quantity=line.quantity,
                unit_price=line.unit_price,
                subtotal=line.subtotal,
                tax_amount=line.tax_amount,
                total_amount=line.total_amount,
            )
            for line in invoice.lines
        ],
        subtotal=invoice.subtotal,
        tax_amount=invoice.tax_amount,
        total_amount=invoice.total_amount,
        version=invoice.version,
    )


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
