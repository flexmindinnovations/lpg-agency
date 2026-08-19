"""API router for managing invoices."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from lpg.api.v1.dependencies.accounting import get_credit_note_repository, get_invoice_repository
from lpg.api.v1.dependencies.identity import get_current_principal, require_permission
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.api.v1.schemas.invoice import (
    CreditNoteResponse,
    InvoiceLineResponse,
    InvoicePageResponse,
    InvoiceResponse,
    PaymentResponse,
    RecordPaymentRequest,
    RequestRefundRequest,
)
from lpg.application.accounting.ports import CreditNoteRepository, InvoiceRepository
from lpg.application.accounting.use_cases import (
    ApproveRefundCommand,
    ApproveRefundUseCase,
    GetInvoiceQuery,
    GetInvoiceUseCase,
    ListInvoicesQuery,
    ListInvoicesUseCase,
    RecordPaymentCommand,
    RecordPaymentUseCase,
    RequestRefundCommand,
    RequestRefundUseCase,
)
from lpg.application.common.ports import UnitOfWork
from lpg.application.identity.ports import AuthenticatedPrincipal
from lpg.domain.accounting.credit_note import CreditNote
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
        payments=[
            PaymentResponse(
                payment_id=payment.id,
                method=payment.method,
                amount=payment.amount,
                collected_by=payment.collected_by,
                collected_at=payment.collected_at,
            )
            for payment in invoice.payments
        ],
        amount_paid=invoice.amount_paid,
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


@router.post(
    "/{invoice_id}/payments",
    response_model=InvoiceResponse,
    status_code=201,
    dependencies=[Depends(require_permission("invoices:record_payment"))],
)
async def record_payment(
    invoice_id: uuid.UUID,
    request: RecordPaymentRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> InvoiceResponse:
    """Record a payment against an invoice (R10, `PaymentCollected`,
    BR-18/D-11). Supports partial payments — `status` only reaches `paid`
    once cumulative payments equal `total_amount`.
    """
    if principal.user_id is None:
        raise HTTPException(status_code=401, detail="User ID is required.")
    use_case = RecordPaymentUseCase(repository, unit_of_work)
    invoice = await use_case.execute(
        RecordPaymentCommand(
            invoice_id=invoice_id,
            method=request.method,
            amount=request.amount,
            collected_by=principal.user_id,
            collected_at=datetime.now(UTC),
        )
    )
    return _invoice_to_response(invoice)


def _credit_note_to_response(credit_note: CreditNote) -> CreditNoteResponse:
    return CreditNoteResponse.model_validate(credit_note)


@router.post(
    "/{invoice_id}/refunds",
    response_model=CreditNoteResponse,
    status_code=201,
    dependencies=[Depends(require_permission("credit_notes:request"))],
)
async def request_refund(
    invoice_id: uuid.UUID,
    request: RequestRefundRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    credit_note_repository: Annotated[CreditNoteRepository, Depends(get_credit_note_repository)],
    invoice_repository: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> CreditNoteResponse:
    """Request a refund against an invoice (R10, BR-20). Not yet approved —
    `amount` cannot exceed the invoice's actual `amount_paid`.
    """
    if principal.user_id is None:
        raise HTTPException(status_code=401, detail="User ID is required.")
    use_case = RequestRefundUseCase(credit_note_repository, invoice_repository, unit_of_work)
    credit_note = await use_case.execute(
        RequestRefundCommand(
            invoice_id=invoice_id,
            amount=request.amount,
            reason=request.reason,
            requested_by=principal.user_id,
        )
    )
    return _credit_note_to_response(credit_note)


@router.post(
    "/{invoice_id}/refunds/{credit_note_id}/approve",
    response_model=CreditNoteResponse,
    dependencies=[Depends(require_permission("credit_notes:approve"))],
)
async def approve_refund(
    invoice_id: uuid.UUID,
    credit_note_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    credit_note_repository: Annotated[CreditNoteRepository, Depends(get_credit_note_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> CreditNoteResponse:
    """Approve a previously-requested refund (R10, `RefundApproved`, BR-20).

    `invoice_id` is validated against the credit note's own `invoice_id` —
    a credit note requested against one invoice cannot be approved through
    a different invoice's nested URL.
    """
    if principal.user_id is None:
        raise HTTPException(status_code=401, detail="User ID is required.")
    use_case = ApproveRefundUseCase(credit_note_repository, unit_of_work)
    credit_note = await use_case.execute(
        ApproveRefundCommand(
            invoice_id=invoice_id, credit_note_id=credit_note_id, approved_by=principal.user_id
        )
    )
    return _credit_note_to_response(credit_note)
